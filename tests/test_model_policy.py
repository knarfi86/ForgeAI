from forgeai.ai.model_policy import (
    IdentityModelAdapter,
    ModelProfile,
    ModelTarget,
    PrimaryModelPolicy,
)


def test_primary_policy_keeps_same_model_across_roles():
    policy = PrimaryModelPolicy(ModelProfile("ollama", "gpt-oss:20b"))

    planner = policy.resolve("planner")
    reviewer = policy.resolve("reviewer")
    repairer = policy.resolve("repairer")

    assert planner.target == ModelTarget("ollama", "gpt-oss:20b")
    assert reviewer.target == planner.target
    assert repairer.target == planner.target
    assert all(decision.source == "primary" for decision in policy.decisions())


def test_specialist_is_used_only_when_explicitly_required():
    policy = PrimaryModelPolicy(ModelProfile("ollama", "gpt-oss:20b"))
    policy.register_specialist(
        "coder",
        ModelProfile(
            "ollama",
            "special-coder:latest",
            preferred_roles=("coder",),
            specialist=True,
        ),
    )

    assert policy.resolve("coder").target.model == "gpt-oss:20b"
    assert policy.resolve("coder", specialist_required=True).target.model == "special-coder:latest"


def test_missing_required_specialist_fails_instead_of_silently_falling_back():
    policy = PrimaryModelPolicy(ModelProfile("ollama", "gpt-oss:20b"))

    try:
        policy.resolve("reviewer", specialist_required=True)
    except LookupError as error:
        assert "kein freigegebener Spezialist" in str(error)
    else:
        raise AssertionError("Expected LookupError")


def test_return_to_primary_restores_affinity_after_specialist():
    policy = PrimaryModelPolicy(ModelProfile("ollama", "gpt-oss:20b"))
    policy.register_specialist(
        "coder",
        ModelProfile("ollama", "coder:latest", specialist=True),
    )

    policy.resolve("coder", specialist_required=True)
    assert policy.active_target.model == "coder:latest"

    policy.return_to_primary()
    assert policy.active_target.model == "gpt-oss:20b"


def test_identity_adapter_preserves_forge_contract_inputs():
    adapter = IdentityModelAdapter()
    profile = ModelProfile("ollama", "gpt-oss:20b")

    assert adapter.adapt_prompt(role="planner", prompt="PLAN", profile=profile) == "PLAN"
    assert adapter.adapt_options(
        role="planner",
        options={"temperature": 0.1},
        profile=profile,
    ) == {"temperature": 0.1}
