"""Validation of LLM claims against deterministic project evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum

from forgeai.core.project_evidence import ProjectEvidence


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"


class ClaimType(str, Enum):
    FILE_EXISTS = "file_exists"
    FILE_MISSING = "file_missing"
    FUNCTION_EXISTS = "function_exists"
    CLASS_EXISTS = "class_exists"
    MODULE_EXISTS = "module_exists"
    IMPORT_EXISTS = "import_exists"
    PACKAGE_DEPENDENCY_EXISTS = "package_dependency_exists"
    DEPENDENCY_EXISTS = "dependency_exists"
    SYNTAX_ERROR = "syntax_error"
    DUPLICATE_EVENT_HANDLER = "duplicate_event_handler"
    ARCHITECTURE_PROBLEM = "architecture_problem"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Claim:
    """A model-generated statement that must not be treated as fact yet."""

    statement: str
    claim_type: ClaimType | None = None
    target: str | None = None
    category: str = "analysis"
    source_file: str | None = None
    source_line: int | None = None


@dataclass(frozen=True)
class ClaimValidation:
    claim: Claim
    status: ClaimStatus
    evidence_ids: list[str] = field(default_factory=list)
    reason: str = ""


class EvidenceValidator:
    """Validate model claims against deterministic project evidence."""

    @staticmethod
    def _normalize_package_name(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name).casefold()

    _DUPLICATE_WORDS = (
        "doppelt",
        "doppelte",
        "mehrfach",
        "mehrmals",
        "zweimal",
        "duplicate",
        "duplicated",
        "multiple",
    )

    def validate(
        self,
        claim: Claim,
        evidence: ProjectEvidence,
    ) -> ClaimValidation:
        statement = claim.statement.strip()
        normalized = statement.casefold()

        if claim.claim_type == ClaimType.DUPLICATE_EVENT_HANDLER:
            observations = evidence.matching(
                "event_handler",
                claim.target or "pygame.MOUSEBUTTONDOWN",
            )
            evidence_items = evidence.all_evidence_for(observations)

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                evidence_ids=[
                    item.evidence_id for item in evidence_items
                ],
                reason=(
                    f"{len(observations)} Event-Handler-Fundstelle(n) "
                    "wurden deterministisch erkannt. Das belegt mehrere "
                    "Handler, aber keine tatsächliche doppelte Verarbeitung "
                    "desselben Events."
                ),
            )

        if claim.claim_type == ClaimType.FILE_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für FILE_EXISTS muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "file",
                claim.target,
                scope=claim.source_file,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Die Datei {claim.target} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=f"Die Datei {claim.target} konnte nicht belegt werden.",
            )

        if claim.claim_type == ClaimType.FILE_MISSING:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für FILE_MISSING muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "file",
                claim.target,
                scope=claim.source_file,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.CONTRADICTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Die Datei {claim.target} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=(
                    f"Das Fehlen der Datei {claim.target} wurde nicht "
                    "durch eine vollständige negative Evidenz bestätigt."
                ),
            )

        if claim.claim_type == ClaimType.CLASS_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für CLASS_EXISTS muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "class",
                claim.target,
                scope=claim.source_file,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Die Klasse {claim.target} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=f"Die Klasse {claim.target} konnte nicht belegt werden.",
            )

        if claim.claim_type == ClaimType.MODULE_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für MODULE_EXISTS muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "module",
                claim.target,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Das Modul {claim.target} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=f"Das Modul {claim.target} konnte nicht belegt werden.",
            )

        if claim.claim_type == ClaimType.IMPORT_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für IMPORT_EXISTS muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "import",
                claim.target,
                scope=claim.source_file,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=(
                        f"Der Import {claim.target} wurde"
                        + (
                            f" in {claim.source_file}"
                            if claim.source_file
                            else " im Projekt"
                        )
                        + " gefunden."
                    ),
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=f"Der Import {claim.target} konnte nicht belegt werden.",
            )

        if claim.claim_type == ClaimType.PACKAGE_DEPENDENCY_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="F?r PACKAGE_DEPENDENCY_EXISTS muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "package_dependency",
                self._normalize_package_name(claim.target),
                scope="requirements.txt",
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=(
                        f"Die Paketabh?ngigkeit {claim.target} wurde "
                        "in requirements.txt gefunden."
                    ),
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=(
                    f"Die Paketabh?ngigkeit {claim.target} konnte "
                    "in requirements.txt nicht belegt werden."
                ),
            )

        if claim.claim_type == ClaimType.DEPENDENCY_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für DEPENDENCY_EXISTS muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "dependency",
                claim.target,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Die Abhängigkeit {claim.target} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=f"Die Abhängigkeit {claim.target} konnte nicht belegt werden.",
            )

        if claim.claim_type == ClaimType.SYNTAX_ERROR:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason="Für SYNTAX_ERROR muss ein explizites target angegeben werden.",
                )

            observations = evidence.matching(
                "syntax_error",
                claim.target,
                scope=claim.source_file,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=(
                        f"Der Syntaxfehler {claim.target} wurde"
                        + (
                            f" in {claim.source_file}"
                            if claim.source_file
                            else " im Projekt"
                        )
                        + " nachgewiesen."
                    ),
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=f"Der Syntaxfehler {claim.target} konnte nicht belegt werden.",
            )

        if claim.claim_type == ClaimType.FUNCTION_EXISTS:
            if not claim.target:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.UNVERIFIED,
                    reason=(
                        "Für FUNCTION_EXISTS muss ein explizites "
                        "target angegeben werden."
                    ),
                )

            observations = evidence.matching(
                "function",
                claim.target,
                scope=claim.source_file,
            )

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=(
                        f"Die Funktion {claim.target} wurde"
                        + (
                            f" in {claim.source_file}"
                            if claim.source_file
                            else " im Projekt"
                        )
                        + " gefunden."
                    ),
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=(
                    f"Die Funktion {claim.target} konnte"
                    + (
                        f" in {claim.source_file}"
                        if claim.source_file
                        else " im Projekt"
                    )
                    + " nicht belegt werden."
                ),
            )

        if claim.claim_type in {
            ClaimType.ARCHITECTURE_PROBLEM,
            ClaimType.UNKNOWN,
        }:
            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=(
                    "Für diesen Claim-Typ existiert noch keine "
                    "deterministische Prüfregel."
                ),
            )

        duplicate_event = (
            "mousebuttondown" in normalized
            and any(word in normalized for word in self._DUPLICATE_WORDS)
        )

        if duplicate_event:
            observations = evidence.matching(
                "event_handler",
                "pygame.MOUSEBUTTONDOWN",
            )
            event_count = len(observations)
            evidence_items = evidence.all_evidence_for(observations)

            if event_count >= 2:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id for item in evidence_items
                    ],
                    reason=(
                        f"{event_count} konkrete MOUSEBUTTONDOWN-"
                        "Verarbeitungsstellen wurden im AST gefunden."
                    ),
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                evidence_ids=[
                    item.evidence_id for item in evidence_items
                ],
                reason=(
                    f"Nur {event_count} konkrete MOUSEBUTTONDOWN-"
                    "Verarbeitungsstelle(n) wurden gefunden. "
                    "Das reicht nicht als Nachweis für doppelte Verarbeitung."
                ),
            )

        file_claim = re.search(
            r"""(?:datei|file)\s+[`'"“”]?([\w./\\-]+)[`'"“”]?\s+
            (?:fehlt|nicht vorhanden|existiert nicht)""",
            normalized,
            re.VERBOSE,
        )

        if file_claim:
            path = file_claim.group(1)
            observations = evidence.matching("file", path)

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.CONTRADICTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Die Datei {path} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.SUPPORTED,
                reason=(
                    f"Die Datei {path} wurde im vollständigen Projektindex "
                    "nicht gefunden."
                ),
            )

        positive_function = re.search(
            r"""(?:funktion|function)\s+[`'"]?([A-Za-z_]\w*)""",
            normalized,
        )

        if positive_function:
            name = positive_function.group(1)
            observations = evidence.matching("function", name)

            if observations:
                return ClaimValidation(
                    claim=claim,
                    status=ClaimStatus.SUPPORTED,
                    evidence_ids=[
                        item.evidence_id
                        for item in evidence.all_evidence_for(observations)
                    ],
                    reason=f"Die Funktion {name} wurde im Projekt gefunden.",
                )

            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNVERIFIED,
                reason=(
                    f"Für die Funktion {name} wurde keine positive Evidenz "
                    "gefunden."
                ),
            )

        return ClaimValidation(
            claim=claim,
            status=ClaimStatus.UNVERIFIED,
            reason=(
                "Für diese Behauptung existiert noch keine "
                "deterministische Prüfregel."
            ),
        )

    @staticmethod
    def claims_from_json(payload: str) -> list[Claim]:
        """Parse and validate structured model claims."""
        try:
            data = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return []

        if not isinstance(data, dict):
            return []

        raw_claims = data.get("claims")
        if not isinstance(raw_claims, list):
            return []

        claims: list[Claim] = []

        for item in raw_claims:
            if not isinstance(item, dict):
                continue

            statement = item.get("statement")
            claim_type_value = item.get("claim_type")

            if not isinstance(statement, str) or not statement.strip():
                continue

            if not isinstance(claim_type_value, str):
                continue

            try:
                claim_type = ClaimType(claim_type_value)
            except ValueError:
                continue

            target = item.get("target")
            source_file = item.get("source_file")
            source_line = item.get("source_line")
            category = item.get("category", "analysis")

            if target is not None and not isinstance(target, str):
                continue

            if source_file is not None and not isinstance(source_file, str):
                continue

            if source_line is not None and not isinstance(source_line, int):
                continue

            if not isinstance(category, str):
                category = "analysis"

            claims.append(
                Claim(
                    statement=statement.strip(),
                    claim_type=claim_type,
                    target=target,
                    category=category,
                    source_file=source_file,
                    source_line=source_line,
                )
            )

        return claims
    def validate_many(
        self,
        claims: list[Claim],
        evidence: ProjectEvidence,
    ) -> list[ClaimValidation]:
        return [self.validate(claim, evidence) for claim in claims]

    def rewrite_analysis(
        self,
        response: str,
        evidence: ProjectEvidence,
    ) -> str:
        """Reclassify model claims using deterministic evidence."""
        lines = response.splitlines()

        secure_index = self._find_heading(lines, "sichere fehler")
        risks_index = self._find_heading(lines, "unsichere risiken")
        improvements_index = self._find_heading(
            lines,
            "verbesserungsvorschläge",
        )

        if secure_index is None:
            return response

        secure_end = len(lines)

        if risks_index is not None and risks_index > secure_index:
            secure_end = risks_index

        secure_lines = lines[secure_index + 1:secure_end]

        claims: list[Claim] = []
        original_bullets: list[str] = []

        for line in secure_lines:
            stripped = line.strip()

            if not stripped.startswith(("-", "*")):
                continue

            statement = stripped[1:].strip()

            if not statement:
                continue

            original_bullets.append(statement)
            claims.append(
                Claim(
                    statement=statement,
                    category="error",
                )
            )

        if not claims:
            return response

        validations = self.validate_many(claims, evidence)

        supported: list[tuple[str, ClaimValidation]] = []
        downgraded: list[tuple[str, ClaimValidation]] = []

        for statement, validation in zip(
            original_bullets,
            validations,
        ):
            if validation.status == ClaimStatus.SUPPORTED:
                supported.append((statement, validation))
            else:
                downgraded.append((statement, validation))

        prefix = lines[:secure_index]
        result = prefix + [lines[secure_index]]

        if supported:
            for statement, validation in supported:
                result.append(f"- [BELEGT] {statement}")

                if validation.evidence_ids:
                    result.append(
                        "  Evidence: "
                        + ", ".join(validation.evidence_ids)
                    )

                result.append(
                    f"  Nachweis: {validation.reason}"
                )
        else:
            result.append(
                "- Keine sicher nachweisbaren Fehler im "
                "lokal belegbaren Kontext."
            )

        if risks_index is not None:
            risks_end = len(lines)

            if (
                improvements_index is not None
                and improvements_index > risks_index
            ):
                risks_end = improvements_index

            result.append("")
            result.extend(lines[risks_index:risks_end])

        for statement, validation in downgraded:
            if validation.status == ClaimStatus.CONTRADICTED:
                label = "WIDERLEGT"
            else:
                label = "NICHT BELEGT"

            result.append(
                f"- [{label}] {statement} "
                f"({validation.reason})"
            )

        if improvements_index is not None:
            result.append("")
            result.extend(lines[improvements_index:])

        return "\n".join(result)

    def render_claims(
        self,
        claims: list[Claim],
        evidence: ProjectEvidence,
    ) -> str:
        """Render structured claims only after deterministic validation."""
        validations = self.validate_many(claims, evidence)

        secure_errors: list[str] = []
        risks: list[str] = []
        improvements: list[str] = []
        unverified: list[str] = []

        for validation in validations:
            claim = validation.claim
            statement = claim.statement

            evidence_text = ""
            if validation.evidence_ids:
                evidence_text = (
                    " | Evidence: "
                    + ", ".join(validation.evidence_ids)
                )

            location = ""
            if claim.source_file:
                location = f" | {claim.source_file}"
                if claim.source_line is not None:
                    location += f":{claim.source_line}"

            detail = (
                f"{statement}{location}"
                f" | {validation.reason}{evidence_text}"
            )

            if (
                claim.category == "error"
                and validation.status == ClaimStatus.SUPPORTED
            ):
                secure_errors.append(
                    f"- [BELEGT] {detail}"
                )
            elif claim.category == "risk":
                risks.append(
                    f"- [NICHT BELEGT] {detail}"
                    if validation.status == ClaimStatus.UNVERIFIED
                    else f"- [WIDERLEGT] {detail}"
                )
            elif claim.category == "improvement":
                improvements.append(
                    f"- {statement}"
                )
            else:
                unverified.append(
                    f"- [{validation.status.value.upper()}] {detail}"
                )

        lines = ["1. Sichere Fehler"]

        if secure_errors:
            lines.extend(secure_errors)
        else:
            lines.append(
                "- Keine sicher nachweisbaren Fehler im "
                "lokal belegbaren Kontext."
            )

        lines.extend(["", "2. Unsichere Risiken"])

        if risks:
            lines.extend(risks)
        else:
            lines.append("- Keine zusätzlichen Risiken.")

        lines.extend(["", "3. Verbesserungsvorschläge"])

        if improvements:
            lines.extend(improvements)
        else:
            lines.append("- Keine Vorschläge aus den Claims.")

        if unverified:
            lines.extend(["", "Nicht bestätigte Behauptungen"])
            lines.extend(unverified)

        return "\n".join(lines)
    def render_structured_analysis(
        self,
        payload: dict,
        evidence: ProjectEvidence,
    ) -> str:
        """Render model analysis together with evidence-validated claims."""
        analysis = payload.get("analysis")
        if not isinstance(analysis, dict):
            analysis = {}

        claims = self.claims_from_json(json.dumps(payload, ensure_ascii=False))
        validations = self.validate_many(claims, evidence)

        lines = [
            "Projektanalyse",
            "",
            "1. Zusammenfassung",
            analysis.get("summary") or "Keine Zusammenfassung geliefert.",
            "",
            "2. Architektur",
            analysis.get("architecture") or "Keine Architekturbeschreibung geliefert.",
            "",
            "3. Komponenten",
        ]

        components = analysis.get("components")
        if isinstance(components, list) and components:
            lines.extend(f"- {item}" for item in components if item)
        else:
            lines.append("- Keine Komponentenbeschreibung geliefert.")

        lines.extend([
            "",
            "4. Ablauf",
            analysis.get("flow") or "Keine Ablaufbeschreibung geliefert.",
            "",
            "5. Beobachtungen",
        ])

        observations = analysis.get("observations")
        if isinstance(observations, list) and observations:
            lines.extend(f"- {item}" for item in observations if item)
        else:
            lines.append("- Keine zusätzlichen Beobachtungen geliefert.")

        secure_errors = []
        risks = []
        improvements = []
        unverified = []
        claim_observations = []

        for validation in validations:
            claim = validation.claim
            statement = claim.statement

            location = ""
            if claim.source_file:
                location = f" | {claim.source_file}"
                if claim.source_line is not None:
                    location += f":{claim.source_line}"

            evidence_text = ""
            if validation.evidence_ids:
                evidence_text = (
                    " | Evidence: "
                    + ", ".join(validation.evidence_ids)
                )

            detail = (
                f"{statement}{location}"
                f" | {validation.reason}{evidence_text}"
            )

            if (
                claim.category == "error"
                and validation.status == ClaimStatus.SUPPORTED
            ):
                secure_errors.append(f"- [BELEGT] {detail}")
            elif claim.category == "risk":
                if validation.status == ClaimStatus.UNVERIFIED:
                    risks.append(f"- [NICHT BELEGT] {detail}")
                elif validation.status == ClaimStatus.CONTRADICTED:
                    risks.append(f"- [WIDERLEGT] {detail}")
                else:
                    risks.append(f"- [BELEGT] {detail}")
            elif claim.category == "improvement":
                improvements.append(f"- {statement}")
            elif claim.category == "analysis":
                claim_observations.append(
                    f"- [{validation.status.value.upper()}] {detail}"
                )
            elif claim.category == "error":
                label = (
                    "WIDERLEGT"
                    if validation.status == ClaimStatus.CONTRADICTED
                    else "NICHT BELEGT"
                )
                unverified.append(f"- [{label}] {detail}")
            else:
                unverified.append(
                    f"- [{validation.status.value.upper()}] {detail}"
                )

        lines.extend([
            "",
            "6. Sichere Fehler",
        ])

        if secure_errors:
            lines.extend(secure_errors)
        else:
            lines.append(
                "- Keine sicher nachweisbaren Fehler im "
                "lokal belegbaren Kontext."
            )

        lines.extend([
            "",
            "7. Unsichere Risiken",
        ])

        if risks:
            lines.extend(risks)
        else:
            lines.append("- Keine zusätzlichen Risiken.")

        lines.extend([
            "",
            "8. Verbesserungsvorschläge",
        ])

        if improvements:
            lines.extend(improvements)
        else:
            lines.append("- Keine Verbesserungsvorschläge aus den Claims.")

        if claim_observations:
            lines.extend([
                "",
                "9. Ergänzende prüfbare Beobachtungen",
            ])
            lines.extend(claim_observations)

        if unverified:
            lines.extend([
                "",
                "Nicht bestätigte Behauptungen",
            ])
            lines.extend(unverified)

        return "\n".join(lines)

    @staticmethod
    def _find_heading(
        lines: list[str],
        wanted: str,
    ) -> int | None:
        wanted = wanted.casefold()

        for index, line in enumerate(lines):
            normalized = re.sub(
                r"^\d+\.\s*",
                "",
                line.strip(),
            ).casefold()

            if normalized == wanted:
                return index

        return None








