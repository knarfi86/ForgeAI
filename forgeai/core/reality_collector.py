from __future__ import annotations

from pathlib import Path

from forgeai.core.agent_reality import AgentReality
from forgeai.core.project_evidence import ProjectEvidence


class RealityCollector:
    """Collects deterministic project evidence and attaches it to AgentReality."""

    def __init__(self, analyzer):
        self.analyzer = analyzer

    def collect_project(
        self,
        reality: AgentReality,
        project_path: str | Path,
    ) -> ProjectEvidence:
        project_evidence = ProjectEvidence.from_analyzer(
            self.analyzer,
            project_path,
        )

        self._replace_project_evidence(
            reality,
            project_evidence,
        )

        return project_evidence

    def _replace_project_evidence(
        self,
        reality: AgentReality,
        project_evidence: ProjectEvidence,
    ) -> None:
        old_observation_ids = {
            observation.observation_id
            for observation in reality.observations
            if observation.observation_id.startswith("project:")
        }

        old_evidence_ids = {
            evidence.evidence_id
            for evidence in reality.evidence
            if evidence.evidence_id.startswith("project:")
        }

        reality.observations = [
            observation
            for observation in reality.observations
            if observation.observation_id not in old_observation_ids
        ]

        reality.evidence = [
            evidence
            for evidence in reality.evidence
            if evidence.evidence_id not in old_evidence_ids
        ]

        observation_id_map: dict[str, str] = {}

        for observation in project_evidence.observations:
            original_id = observation.observation_id
            new_id = f"project:{original_id}"

            observation_id_map[original_id] = new_id
            observation.observation_id = new_id
            reality.observations.append(observation)

        for evidence in project_evidence.evidence:
            evidence.evidence_id = f"project:{evidence.evidence_id}"

            evidence.observation_ids = [
                observation_id_map.get(
                    observation_id,
                    observation_id,
                )
                for observation_id in evidence.observation_ids
            ]

            reality.evidence.append(evidence)
