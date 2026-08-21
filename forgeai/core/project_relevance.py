"""Deterministic project-file relevance ranking for local agent research."""

from pathlib import Path
import json
import re


class ProjectRelevance:
    """Ranks indexed project files against a user request without using AI."""

    MAX_RESULTS = 8

    STOP_WORDS = {
        "aber", "alle", "als", "auch", "auf", "aus", "bei", "damit",
        "dass", "der", "die", "dies", "diese", "dieser", "ein", "eine",
        "einer", "einem", "einen", "für", "gegen", "hat", "haben",
        "hier", "ich", "im", "in", "ist", "kann", "mit", "nach", "nicht",
        "nur", "oder", "sich", "sie", "sind", "und", "von", "war", "warum",
        "wie", "wird", "zu", "zum", "zur", "zusammen", "richtig", "damit",
        "lesen", "forge", "funktioniert",
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
        terms = self._terms(request)

        if not terms:
            return []

        records = self.database.fetchall(
            "SELECT relative_path FROM project_files "
            "WHERE project_path=? ORDER BY relative_path",
            (str(root),),
        )

        analysis = self._load_analysis(root)
        imports = analysis.get("imports", {})
        dependency_graph = analysis.get("dependency_graph", {})

        scored: list[tuple[int, str]] = []

        for record in records:
            relative_path = record["relative_path"]
            path_score = self._score_path(relative_path, terms)

            import_score = 0
            dependency_score = 0

            if relative_path in imports:
                import_score = self._score_imports(imports[relative_path], terms)

            module = self._module_name(relative_path)

            if module in dependency_graph:
                dependency_score = self._score_imports(
                    dependency_graph[module],
                    terms,
                )

            relationship_score = max(import_score, dependency_score)
            score = path_score + relationship_score

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
            return json.loads(row["analysis_json"])
        except (TypeError, ValueError):
            return {}

    @classmethod
    def _terms(cls, request: str) -> list[str]:
        normalized = request.casefold()

        separators = (
            ".", ",", ":", ";", "!", "?", "(", ")", "[", "]",
            "{", "}", "/", "\\", '"', "'", "`", "\n", "\r", "\t",
        )

        for separator in separators:
            normalized = normalized.replace(separator, " ")

        return sorted(
            {
                term
                for term in normalized.split()
                if len(term) >= 3 and term not in cls.STOP_WORDS
            },
            key=lambda term: (-len(term), term),
        )

    @classmethod
    def _score_path(cls, relative_path: str, terms: list[str]) -> int:
        path = relative_path.casefold()
        filename = Path(relative_path).name.casefold()
        stem = Path(relative_path).stem.casefold()

        score = 0

        for term in terms:
            if term == filename:
                score += 100
            elif term == stem:
                score += 90
            elif term in filename:
                score += 25
            elif term in path:
                score += 5

        for class_name in cls._class_like_terms(terms):
            normalized_class = re.sub(r"[^a-z0-9]", "", class_name.casefold())
            normalized_stem = re.sub(r"[^a-z0-9]", "", stem)

            if normalized_class == normalized_stem:
                score += 80

        return score

    @staticmethod
    def _class_like_terms(terms: list[str]) -> list[str]:
        result = []

        for term in terms:
            if "_" in term:
                parts = term.split("_")

                if all(parts):
                    result.append("".join(part.capitalize() for part in parts))

        return result

    @staticmethod
    def _score_imports(imports: list[str], terms: list[str]) -> int:
        if not isinstance(imports, list):
            return 0

        score = 0

        for imported in imports:
            value = str(imported).casefold()

            for term in terms:
                if term == value:
                    score += 8
                elif term in value:
                    score += 3

        return score

    @staticmethod
    def _module_name(relative_path: str) -> str:
        path = Path(relative_path).with_suffix("")

        if path.name == "__init__":
            return ".".join(path.parts[:-1])

        return ".".join(path.parts)
