from datetime import datetime, timedelta, timezone

import pytest

from forgeai.ai.agent_orchestrator import AgentOrchestrator
from forgeai.ai.agent_state import AgentRun
from forgeai.core.agent_reality import RunReality
from forgeai.core.fact_evidence_provider import (
    FactContext,
    FactObservation,
    FactQuery,
    FactRegistry,
    FactService,
    FactSourceType,
    FactStatus,
    FunctionFactProvider,
)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def provider(callback, *, provider_id="fs.exists", keys=("filesystem.exists",)):
    return FunctionFactProvider(
        provider_id=provider_id,
        source_type=FactSourceType.FILESYSTEM,
        fact_keys=keys,
        callback=callback,
    )


def test_registry_registers_machine_fact_provider():
    registry = FactRegistry()
    registry.register_provider(provider(lambda context, query: FactObservation(
        FactStatus.OBSERVED, True, "exists"
    )))

    assert registry.list_provider_ids() == ("fs.exists",)
    assert registry.resolve_provider(FactQuery("filesystem.exists")).provider_id == "fs.exists"


def test_registry_requires_explicit_provider_when_multiple_sources_support_same_fact():
    registry = FactRegistry()
    registry.register_provider(provider(lambda c, q: FactObservation(FactStatus.OBSERVED, True)))
    registry.register_provider(provider(
        lambda c, q: FactObservation(FactStatus.OBSERVED, True),
        provider_id="fs.exists.second",
    ))

    with pytest.raises(ValueError, match="provider_id"):
        registry.resolve_provider(FactQuery("filesystem.exists"))

    selected = registry.resolve_provider(FactQuery(
        "filesystem.exists", provider_id="fs.exists.second"
    ))
    assert selected.provider_id == "fs.exists.second"


def test_positive_ttl_reuses_fresh_observation_but_zero_ttl_rechecks():
    calls = []

    def observe(context, query):
        calls.append(1)
        return FactObservation(FactStatus.OBSERVED, len(calls), "observed")

    registry = FactRegistry()
    registry.register_provider(provider(observe))
    clock = Clock()
    service = FactService(registry, clock=clock)
    context = FactContext("task-1", 1, "C:/project")

    first = service.resolve(FactQuery("filesystem.exists", max_age_seconds=30), context)
    second = service.resolve(FactQuery("filesystem.exists", max_age_seconds=30), context)
    always_fresh = service.resolve(FactQuery("filesystem.exists", max_age_seconds=0), context)

    assert first.used_cache is False
    assert second.used_cache is True
    assert second.record.fact_id == first.record.fact_id
    assert always_fresh.used_cache is False
    assert len(calls) == 2


def test_stale_fact_is_reobserved_after_ttl():
    calls = []

    def observe(context, query):
        calls.append(1)
        return FactObservation(FactStatus.OBSERVED, len(calls), "observed")

    registry = FactRegistry()
    registry.register_provider(provider(observe))
    clock = Clock()
    service = FactService(registry, clock=clock)
    query = FactQuery("filesystem.exists", max_age_seconds=10)
    context = FactContext("task-1", 1)

    first = service.resolve(query, context)
    clock.advance(11)
    second = service.resolve(query, context)

    assert second.used_cache is False
    assert second.replaced_fact_id == first.record.fact_id
    assert second.record.fact_id != first.record.fact_id
    assert "fact_refreshed" in second.reason_codes


def test_new_execution_round_never_reuses_previous_round_fact():
    calls = []

    def observe(context, query):
        calls.append(context.execution_round)
        return FactObservation(FactStatus.OBSERVED, context.execution_round, "round")

    registry = FactRegistry()
    registry.register_provider(provider(observe))
    service = FactService(registry, clock=Clock())
    query = FactQuery("filesystem.exists", max_age_seconds=3600)

    first = service.resolve(query, FactContext("task-1", 1))
    second = service.resolve(query, FactContext("task-1", 2))

    assert first.record.value == 1
    assert second.record.value == 2
    assert second.used_cache is False
    assert calls == [1, 2]


def test_non_authoritative_absence_is_downgraded_to_unknown():
    registry = FactRegistry()
    registry.register_provider(provider(lambda c, q: FactObservation(
        status=FactStatus.ABSENT,
        summary="not found in partial scan",
        authoritative_absence=False,
    )))
    resolution = FactService(registry, clock=Clock()).resolve(
        FactQuery("filesystem.exists"), FactContext("task-1", 1)
    )

    assert resolution.record.status == FactStatus.UNKNOWN
    assert resolution.record.authoritative is False
    assert "non_authoritative_absence_downgraded" in resolution.reason_codes


def test_unknown_or_error_observation_is_not_reused_as_fresh_truth():
    calls = []

    def observe(context, query):
        calls.append(1)
        return FactObservation(FactStatus.UNKNOWN, summary="not proven")

    registry = FactRegistry()
    registry.register_provider(provider(observe))
    service = FactService(registry, clock=Clock())
    query = FactQuery("filesystem.exists", max_age_seconds=3600)
    context = FactContext("task-1", 1)

    first = service.resolve(query, context)
    second = service.resolve(query, context)

    assert first.record.authoritative is False
    assert second.used_cache is False
    assert len(calls) == 2


def test_authoritative_absence_is_a_valid_fact():
    registry = FactRegistry()
    registry.register_provider(provider(lambda c, q: FactObservation(
        status=FactStatus.ABSENT,
        summary="complete filesystem check",
        authoritative_absence=True,
        tool="pathlib.Path.exists",
    )))
    resolution = FactService(registry, clock=Clock()).resolve(
        FactQuery("filesystem.exists"), FactContext("task-1", 1)
    )

    assert resolution.record.status == FactStatus.ABSENT
    assert resolution.record.authoritative is True
    assert resolution.record.tool == "pathlib.Path.exists"


def test_provider_exception_becomes_error_not_fake_fact():
    def explode(context, query):
        raise RuntimeError("API unavailable")

    registry = FactRegistry()
    registry.register_provider(provider(explode))
    resolution = FactService(registry, clock=Clock()).resolve(
        FactQuery("filesystem.exists"), FactContext("task-1", 1)
    )

    assert resolution.record.status == FactStatus.ERROR
    assert resolution.record.authoritative is False
    assert resolution.record.details["error_type"] == "RuntimeError"
    assert "provider_error" in resolution.reason_codes


def test_orchestrator_resolves_and_records_fact_in_run_and_reality_projection():
    registry = FactRegistry()
    registry.register_provider(provider(lambda c, q: FactObservation(
        FactStatus.OBSERVED,
        value=True,
        summary="path exists",
        tool="filesystem",
    )))
    service = FactService(registry, clock=Clock())
    run = AgentRun("task-1")
    orchestrator = AgentOrchestrator(run, fact_service=service)
    orchestrator.begin_execution()

    resolution = orchestrator.resolve_fact(
        FactQuery("filesystem.exists"),
        project_path="C:/project",
    )

    assert run.fact_history[-1] == resolution.record
    projected = RunReality.from_agent_run(run, run_id="run-1")
    assert projected.fact_history[-1]["fact_key"] == "filesystem.exists"
    assert projected.fact_history[-1]["status"] == FactStatus.OBSERVED


def test_orchestrator_requires_configured_fact_service():
    orchestrator = AgentOrchestrator(AgentRun("task-1"))
    with pytest.raises(RuntimeError, match="FactService"):
        orchestrator.resolve_fact(FactQuery("filesystem.exists"))
