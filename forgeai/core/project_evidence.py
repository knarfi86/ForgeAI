"""Deterministic project evidence derived from ProjectAnalyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from forgeai.core.agent_reality import (
    Evidence,
    EvidenceRelation,
    Observation,
    RealityConfidence,
    RealitySource,
)
from forgeai.core.project_analyzer import ProjectAnalyzer


@dataclass
class ProjectEvidence:
    """Snapshot of facts that were deterministically observed in a project."""

    project_path: str
    observations: list[Observation] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    @classmethod
    def from_analyzer(
        cls,
        analyzer: ProjectAnalyzer,
        project_path: str | Path,
    ) -> "ProjectEvidence":
        analysis = analyzer.analyze(project_path)
        summary = analyzer.evidence_summary(project_path)

        result = cls(project_path=str(analysis["project_path"]))

        for path in analysis.get("files", []):
            result._add_observation(
                "file",
                path,
                f"Datei {path} existiert.",
                scope=path,
            )

        for path, names in analysis.get("classes", {}).items():
            for name in names:
                result._add_observation(
                    "class",
                    name,
                    f"Klasse {name} existiert in {path}.",
                    scope=path,
                )

        for path, names in summary.get("functions", {}).items():
            for name in names:
                result._add_observation(
                    "function",
                    name,
                    f"Funktion {name} existiert in {path}.",
                    scope=path,
                )

        for path, names in analysis.get("imports", {}).items():
            for name in names:
                result._add_observation(
                    "import",
                    name,
                    f"Import {name} existiert in {path}.",
                    scope=path,
                )

        for package in summary.get("package_dependencies", []):
            result._add_observation(
                "package_dependency",
                package,
                f"Paketabh?ngigkeit {package} ist in requirements.txt deklariert.",
                scope="requirements.txt",
            )

        for path, names in summary.get("event_handlers", {}).items():
            for name in names:
                result._add_observation(
                    "event_handler",
                    name,
                    f"Ereignispr?fung {name} wurde in {path} gefunden.",
                    scope=path,
                )

        for module in analysis.get("modules", []):
            result._add_observation(
                "module",
                module,
                f"Modul {module} existiert im Projekt.",
            )

        for module, dependencies in analysis.get("dependency_graph", {}).items():
            for dependency in dependencies:
                result._add_observation(
                    "dependency",
                    f"{module} -> {dependency}",
                    f"Das Modul {module} importiert {dependency}.",
                    scope=module,
                )

        for path, message in summary.get("syntax_errors", {}).items():
            result._add_observation(
                "syntax_error",
                message,
                f"Syntaxfehler in {path}: {message}",
                scope=path,
            )

        for path, names in summary.get("event_retrievals", {}).items():
            for name in names:
                result._add_observation(
                    "event_retrieval",
                    name,
                    f"Ereignisabruf {name} wurde in {path} gefunden.",
                    scope=path,
                )

        return result

    def _add_observation(
        self,
        observation_type: str,
        value: str,
        summary: str,
        *,
        scope: str | None = None,
    ) -> None:
        observation_id = f"observation:{len(self.observations) + 1}"

        observation = Observation(
            observation_id=observation_id,
            type=observation_type,
            source=RealitySource.TOOL,
            summary=summary,
            value=value,
            scope=scope,
            success=True,
        )
        self.observations.append(observation)

        self.evidence.append(
            Evidence(
                evidence_id=f"evidence:{len(self.evidence) + 1}",
                relation=EvidenceRelation.SUPPORTS,
                statement=summary,
                source=RealitySource.TOOL,
                observation_ids=[observation_id],
                confidence=RealityConfidence.HIGH,
            )
        )

    def matching(
        self,
        observation_type: str,
        value: str,
        *,
        scope: str | None = None,
    ) -> list[Observation]:
        normalized = value.casefold()

        return [
            observation
            for observation in self.observations
            if observation.type == observation_type
            and str(observation.value).casefold() == normalized
            and (
                scope is None
                or str(observation.scope).casefold() == scope.casefold()
            )
        ]

    def count(
        self,
        observation_type: str,
        value: str,
        *,
        scope: str | None = None,
    ) -> int:
        return len(
            self.matching(
                observation_type,
                value,
                scope=scope,
            )
        )

    def all_evidence_for(self, observations: list[Observation]) -> list[Evidence]:
        ids = {observation.observation_id for observation in observations}
        return [
            item for item in self.evidence
            if any(observation_id in ids for observation_id in item.observation_ids)
        ]

