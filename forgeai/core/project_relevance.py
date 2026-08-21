"""Deterministic project-file relevance ranking for local agent research."""

from pathlib import Path
import json
import re


class ProjectRelevance:
    """Ranks indexed project files using stored structural project analysis."""

    MAX_RESULTS = 8

    STOP_WORDS = {
        "aber", "alle", "als", "auch", "auf", "aus", "bei", "damit",
        "dass", "der", "die", "dies", "diese", "dieser", "ein", "eine",
        "einer", "einem", "einen", "f?r", "gegen", "hat", "haben",
        "hier", "ich", "im", "in", "ist", "kann", "mit", "nach", "nicht",
        "nur", "oder", "sich", "sie", "sind", "und", "von", "war", "warum",
        "wie", "wird", "zu", "zum", "zur", "zusammen", "richtig",
        "lesen", "forge", "funktioniert", "warum", "wieso",
    }

    def __init__(self, database, filesystem):
        self.database = database
        self.filesystem = filesystem

    def find_relevant(
        self,
        project_path: str | Path,
        request: str,
        max_results: int | None = None,
    ) -> list[str]:
        """Return the most relevant project files for a request."""
        root = self.filesystem.resolve(project_path)
        limit = max_results or self.MAX_RESULTS

        if limit <= 0:
            return []

        terms = self._terms(request)
        if not terms:
            return []

        records = self.database.fetchall(
            "SELECT relative_path FROM project_files "
            "WHERE project_path=? ORDER BY relative_path",
            (str(root),),
        )

        analysis = self._load_analysis(root)
        if not analysis:
            return self._fallback_path_search(records, terms, limit)

        classes = analysis.get("classes", {})
        imports = analysis.get("imports", {})
        modules = analysis.get("modules", [])
        dependency_graph = analysis.get("dependency_graph", {})

        module_by_path = {
            relative_path: self._module_name(relative_path)
            for relative_path in (record["relative_path"] for record in records)
        }

        scored: list[tuple[int, str]] = []

        for record in records:
            relative_path = record["relative_path"]
            module = module_by_path[relative_path]

            score = 0
            score += self._score_path(relative_path, terms)
            score += self._score_classes(classes.get(relative_path, []), terms)
            score += self._score_module(module, modules, terms)
            score += self._score_imports(imports.get(relative_path, []), terms)
            score += self._score_dependencies(
                module,
                dependency_graph,
                terms,
            )

            if score > 0:
                scored.append((score, relative_path))

        scored.sort(key=lambda item: (-item[0], item[1].casefold()))
        return [relative_path for _, relative_path in scored[:limit]]

    def _load_analysis(self, root: Path) -> dict:
        row = self.database.fetchone(
            "SELECT analysis_json FROM project_analysis WHERE project_path=?",
            (str(root),),
        )

        if not row:
            return {}

        try:
            analysis = json.loads(row["analysis_json"])
        except (TypeError, ValueError):
            return {}

        return analysis if isinstance(analysis, dict) else {}

    def _fallback_path_search(self, records, terms: list[str], limit: int) -> list[str]:
        """Keep relevance useful if structural analysis is temporarily unavailable."""
        scored = []

        for record in records:
            relative_path = record["relative_path"]
            score = self._score_path(relative_path, terms)

            if score > 0:
                scored.append((score, relative_path))

        scored.sort(key=lambda item: (-item[0], item[1].casefold()))
        return [relative_path for _, relative_path in scored[:limit]]

    @classmethod
    def _terms(cls, request: str) -> list[str]:
        normalized = request.casefold()

        normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)

        terms = {
            term
            for term in normalized.split()
            if len(term) >= 3 and term not in cls.STOP_WORDS
        }

        return sorted(terms, key=lambda term: (-len(term), term))

    @staticmethod
    def _score_path(relative_path: str, terms: list[str]) -> int:
        path = relative_path.casefold()
        filename = Path(relative_path).name.casefold()
        stem = Path(relative_path).stem.casefold()

        score = 0

        for term in terms:
            if term == filename:
                score += 120
            elif term == stem:
                score += 110
            elif term in filename:
                score += 35
            elif term in path:
                score += 8

        return score

    @staticmethod
    def _score_classes(classes: list[str], terms: list[str]) -> int:
        if not isinstance(classes, list):
            return 0

        score = 0

        for class_name in classes:
            value = str(class_name).casefold()
            normalized_value = re.sub(r"[^\w]+", "", value, flags=re.UNICODE)

            for term in terms:
                normalized_term = re.sub(
                    r"[^\w]+",
                    "",
                    term.casefold(),
                    flags=re.UNICODE,
                )

                if not normalized_term:
                    continue

                if normalized_value == normalized_term:
                    score += 130
                elif normalized_term in normalized_value:
                    score += 40

        return score

    @staticmethod
    def _score_module(
        module: str,
        modules: list[str],
        terms: list[str],
    ) -> int:
        if not isinstance(modules, list):
            return 0

        value = str(module).casefold()
        parts = set(value.split("."))

        score = 0

        for term in terms:
            if term == value:
                score += 100
            elif term in parts:
                score += 45
            elif term in value:
                score += 15

        return score

    @staticmethod
    def _score_imports(imports: list[str], terms: list[str]) -> int:
        if not isinstance(imports, list):
            return 0

        score = 0

        for imported in imports:
            value = str(imported).casefold()
            parts = set(value.lstrip(".").split("."))

            for term in terms:
                if term == value:
                    score += 30
                elif term in parts:
                    score += 18
                elif term in value:
                    score += 6

        return score

    @classmethod
    def _score_dependencies(
        cls,
        module: str,
        dependency_graph: dict,
        terms: list[str],
    ) -> int:
        if not isinstance(dependency_graph, dict):
            return 0

        imported_modules = dependency_graph.get(module, [])
        if not isinstance(imported_modules, list):
            return 0

        score = 0

        for imported in imported_modules:
            value = str(imported).casefold().lstrip(".")
            parts = set(value.split("."))

            for term in terms:
                if term == value:
                    score += 24
                elif term in parts:
                    score += 14
                elif term in value:
                    score += 5

        return score

    @staticmethod
    def _module_name(relative_path: str) -> str:
        path = Path(relative_path).with_suffix("")

        if path.name == "__init__":
            return ".".join(path.parts[:-1])

        return ".".join(path.parts)
