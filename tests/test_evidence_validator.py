from forgeai.core.evidence_validator import (
    Claim,
    ClaimStatus,
    EvidenceValidator,
)
from forgeai.core.project_evidence import ProjectEvidence


def make_evidence(*event_names):
    evidence = ProjectEvidence(project_path="C:/demo")

    for index, event_name in enumerate(event_names, start=1):
        evidence._add_observation(
            "event_handler",
            event_name,
            f"Ereignispr?fung {event_name} wurde in main.py gefunden.",
            scope="main.py",
        )

    return evidence


def test_duplicate_mouse_event_is_supported_when_two_sites_exist():
    validator = EvidenceValidator()
    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
        "pygame.MOUSEBUTTONDOWN",
    )

    result = validator.validate(
        Claim(
            "Doppelte MOUSEBUTTONDOWN-Verarbeitung wurde festgestellt.",
            category="error",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED
    assert len(result.evidence_ids) == 2


def test_duplicate_mouse_event_is_unverified_when_only_one_site_exists():
    validator = EvidenceValidator()
    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
    )

    result = validator.validate(
        Claim(
            "Doppelte MOUSEBUTTONDOWN-Verarbeitung wurde festgestellt.",
            category="error",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.UNVERIFIED
    assert "reicht nicht als Nachweis" in result.reason


def test_unknown_claim_is_unverified():
    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")

    result = validator.validate(
        Claim(
            "Die Spiellogik ist m?glicherweise fehlerhaft.",
            category="error",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.UNVERIFIED


def test_missing_file_can_be_supported_by_complete_file_index():
    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "file",
        "main.py",
        "Datei main.py existiert.",
        scope="main.py",
    )

    result = validator.validate(
        Claim(
            "Datei config.py fehlt.",
            category="error",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_existing_file_contradicts_missing_file_claim():
    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "file",
        "config.py",
        "Datei config.py existiert.",
        scope="config.py",
    )

    result = validator.validate(
        Claim(
            "Datei config.py fehlt.",
            category="error",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.CONTRADICTED


def test_rewrite_moves_unverified_secure_error_to_risks():
    validator = EvidenceValidator()

    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
    )

    response = """1. Sichere Fehler
- Doppelte MOUSEBUTTONDOWN-Verarbeitung wurde festgestellt.

2. Unsichere Risiken
- M?glicherweise fehlt eine Ressource.

3. Verbesserungsvorschl?ge
- Logging verbessern.
"""

    rewritten = validator.rewrite_analysis(response, evidence)

    assert "[WIDERLEGT]" not in rewritten.split("2. Unsichere Risiken", 1)[0]
    assert "[NICHT BELEGT] Doppelte MOUSEBUTTONDOWN-Verarbeitung wurde festgestellt." in rewritten
    assert "Keine sicher nachweisbaren Fehler" in rewritten


def test_claim_type_can_be_explicit():
    from forgeai.core.evidence_validator import ClaimType

    claim = Claim(
        "Doppelte MOUSEBUTTONDOWN-Verarbeitung wurde festgestellt.",
        claim_type=ClaimType.DUPLICATE_EVENT_HANDLER,
        category="error",
    )

    assert claim.claim_type == ClaimType.DUPLICATE_EVENT_HANDLER


def test_explicit_duplicate_event_claim_uses_evidence_rule():
    from forgeai.core.evidence_validator import ClaimType

    validator = EvidenceValidator()
    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
        "pygame.MOUSEBUTTONDOWN",
    )

    result = validator.validate(
        Claim(
            "Beliebiger Text zur Mausverarbeitung.",
            claim_type=ClaimType.DUPLICATE_EVENT_HANDLER,
        ),
        evidence,
    )

    assert result.status == ClaimStatus.UNVERIFIED
    assert len(result.evidence_ids) == 2


def test_explicit_function_claim_uses_evidence_rule():
    from forgeai.core.evidence_validator import ClaimType

    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")

    evidence._add_observation(
        "function",
        "run_game",
        "Funktion run_game existiert in main.py.",
        scope="main.py",
    )

    result = validator.validate(
        Claim(
            "Der Spielstart funktioniert korrekt.",
            claim_type=ClaimType.FUNCTION_EXISTS,
            target="run_game",
            source_file="main.py",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED
    assert len(result.evidence_ids) == 1


def test_unknown_explicit_claim_type_is_unverified():
    from forgeai.core.evidence_validator import ClaimType

    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")

    result = validator.validate(
        Claim(
            "Irgendeine Behauptung.",
            claim_type=ClaimType.ARCHITECTURE_PROBLEM,
        ),
        evidence,
    )

    assert result.status == ClaimStatus.UNVERIFIED

def test_claim_has_explicit_target():
    from forgeai.core.evidence_validator import ClaimType

    claim = Claim(
        statement="Die Funktion run_game existiert.",
        claim_type=ClaimType.FUNCTION_EXISTS,
        target="run_game",
        source_file="main.py",
    )

    assert claim.target == "run_game"
    assert claim.source_file == "main.py"


def test_function_claim_uses_target_not_statement_parsing():
    from forgeai.core.evidence_validator import ClaimType

    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")

    evidence._add_observation(
        "function",
        "run_game",
        "Funktion run_game existiert in main.py.",
        scope="main.py",
    )

    result = validator.validate(
        Claim(
            statement="Der Spielstart funktioniert korrekt.",
            claim_type=ClaimType.FUNCTION_EXISTS,
            target="run_game",
            source_file="main.py",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_function_claim_without_target_is_unverified():
    from forgeai.core.evidence_validator import ClaimType

    validator = EvidenceValidator()
    evidence = ProjectEvidence(project_path="C:/demo")

    result = validator.validate(
        Claim(
            statement="Die Funktion run_game existiert.",
            claim_type=ClaimType.FUNCTION_EXISTS,
        ),
        evidence,
    )

    assert result.status == ClaimStatus.UNVERIFIED
    assert "target" in result.reason


def test_file_exists_claim_is_supported():
    from forgeai.core.evidence_validator import ClaimType

    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "file",
        "config.py",
        "Datei config.py existiert.",
        scope="config.py",
    )

    result = EvidenceValidator().validate(
        Claim(
            "Die Datei config.py existiert.",
            claim_type=ClaimType.FILE_EXISTS,
            target="config.py",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_file_exists_claim_is_unverified_without_target():
    from forgeai.core.evidence_validator import ClaimType

    result = EvidenceValidator().validate(
        Claim(
            "Die Datei config.py existiert.",
            claim_type=ClaimType.FILE_EXISTS,
        ),
        ProjectEvidence(project_path="C:/demo"),
    )

    assert result.status == ClaimStatus.UNVERIFIED
    assert "target" in result.reason


def test_class_exists_claim_is_supported():
    from forgeai.core.evidence_validator import ClaimType

    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "class",
        "Game",
        "Klasse Game existiert in game.py.",
        scope="game.py",
    )

    result = EvidenceValidator().validate(
        Claim(
            "Die Klasse Game existiert.",
            claim_type=ClaimType.CLASS_EXISTS,
            target="Game",
            source_file="game.py",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_module_exists_claim_is_supported():
    from forgeai.core.evidence_validator import ClaimType

    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "module",
        "game",
        "Modul game existiert im Projekt.",
    )

    result = EvidenceValidator().validate(
        Claim(
            "Das Modul game existiert.",
            claim_type=ClaimType.MODULE_EXISTS,
            target="game",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_import_exists_claim_is_supported():
    from forgeai.core.evidence_validator import ClaimType

    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "import",
        "pygame",
        "Import pygame existiert in main.py.",
        scope="main.py",
    )

    result = EvidenceValidator().validate(
        Claim(
            "pygame wird importiert.",
            claim_type=ClaimType.IMPORT_EXISTS,
            target="pygame",
            source_file="main.py",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_dependency_exists_claim_is_supported():
    from forgeai.core.evidence_validator import ClaimType

    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "dependency",
        "main -> game",
        "Das Modul main importiert game.",
        scope="main",
    )

    result = EvidenceValidator().validate(
        Claim(
            "main hÃ¤ngt von game ab.",
            claim_type=ClaimType.DEPENDENCY_EXISTS,
            target="main -> game",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED


def test_syntax_error_claim_is_supported():
    from forgeai.core.evidence_validator import ClaimType

    evidence = ProjectEvidence(project_path="C:/demo")
    evidence._add_observation(
        "syntax_error",
        "invalid syntax",
        "Syntaxfehler in main.py: invalid syntax",
        scope="main.py",
    )

    result = EvidenceValidator().validate(
        Claim(
            "main.py enthÃ¤lt einen Syntaxfehler.",
            claim_type=ClaimType.SYNTAX_ERROR,
            target="invalid syntax",
            source_file="main.py",
        ),
        evidence,
    )

    assert result.status == ClaimStatus.SUPPORTED

def test_structured_claim_contains_required_fields():
    from forgeai.core.evidence_validator import ClaimType

    claim = Claim(
        statement="Doppelte Mausverarbeitung.",
        claim_type=ClaimType.DUPLICATE_EVENT_HANDLER,
        target="pygame.MOUSEBUTTONDOWN",
        source_file="main.py",
        source_line=42,
        category="error",
    )

    assert claim.claim_type == ClaimType.DUPLICATE_EVENT_HANDLER
    assert claim.target == "pygame.MOUSEBUTTONDOWN"
    assert claim.source_file == "main.py"
    assert claim.source_line == 42
    assert claim.category == "error"


def test_structured_analysis_claim_is_supported_by_evidence():
    from forgeai.core.evidence_validator import ClaimType

    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
        "pygame.MOUSEBUTTONDOWN",
    )

    claim = Claim(
        statement="Doppelte Mausverarbeitung.",
        claim_type=ClaimType.DUPLICATE_EVENT_HANDLER,
        target="pygame.MOUSEBUTTONDOWN",
        source_file="main.py",
        category="error",
    )

    result = EvidenceValidator().validate(claim, evidence)

    assert result.status == ClaimStatus.UNVERIFIED
    assert len(result.evidence_ids) == 2


def test_structured_analysis_unknown_claim_remains_unverified():
    from forgeai.core.evidence_validator import ClaimType

    claim = Claim(
        statement="Die Architektur kÃ¶nnte problematisch sein.",
        claim_type=ClaimType.ARCHITECTURE_PROBLEM,
        target="architecture",
        category="risk",
    )

    result = EvidenceValidator().validate(
        claim,
        ProjectEvidence(project_path="C:/demo"),
    )

    assert result.status == ClaimStatus.UNVERIFIED


def test_structured_analysis_can_separate_error_and_risk_categories():
    from forgeai.core.evidence_validator import ClaimType

    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
        "pygame.MOUSEBUTTONDOWN",
    )

    claims = [
        Claim(
            statement="Doppelte Mausverarbeitung.",
            claim_type=ClaimType.DUPLICATE_EVENT_HANDLER,
            target="pygame.MOUSEBUTTONDOWN",
            source_file="main.py",
            category="error",
        ),
        Claim(
            statement="Die Architektur kÃ¶nnte spÃ¤ter schwer wartbar werden.",
            claim_type=ClaimType.ARCHITECTURE_PROBLEM,
            target="architecture",
            category="risk",
        ),
    ]

    results = EvidenceValidator().validate_many(claims, evidence)

    assert results[0].status == ClaimStatus.UNVERIFIED
    assert results[1].status == ClaimStatus.UNVERIFIED
    assert claims[0].category == "error"
    assert claims[1].category == "risk"

def test_structured_claim_payload_is_validated():
    import json

    from forgeai.core.evidence_validator import ClaimType

    validator = EvidenceValidator()

    evidence = make_evidence(
        "pygame.MOUSEBUTTONDOWN",
        "pygame.MOUSEBUTTONDOWN",
    )

    payload = {
        "claims": [
            {
                "claim_type": ClaimType.DUPLICATE_EVENT_HANDLER.value,
                "statement": "Doppelte Mausverarbeitung.",
                "target": "pygame.MOUSEBUTTONDOWN",
                "source_file": "main.py",
                "source_line": 42,
                "category": "error",
            }
        ]
    }

    claims = validator.claims_from_json(json.dumps(payload))

    assert len(claims) == 1
    assert claims[0].claim_type == ClaimType.DUPLICATE_EVENT_HANDLER
    assert claims[0].target == "pygame.MOUSEBUTTONDOWN"

    result = validator.validate_many(claims, evidence)[0]

    assert result.status == ClaimStatus.UNVERIFIED
    assert len(result.evidence_ids) == 2


def test_invalid_structured_claim_payload_is_rejected():
    validator = EvidenceValidator()

    claims = validator.claims_from_json(
        '{"claims": [{"statement": "kaputt"}]}'
    )

    assert claims == []

