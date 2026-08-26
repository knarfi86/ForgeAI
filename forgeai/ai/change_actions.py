"""Translate explicitly marked model actions into safe workspace previews."""

import json


from forgeai.core.workspace_tools import ChangePreview, WorkspaceTools


def extract_change_previews(
    response: str,
    workspace: WorkspaceTools,
) -> tuple[str, list[ChangePreview], list[str]]:
    """Remove action blocks from a response and turn valid ones into previews."""

    previews: list[ChangePreview] = []
    errors: list[str] = []

    visible_response = response.strip()

    try:
        structured = json.loads(response)

        if (
            isinstance(structured, dict)
            and isinstance(structured.get("actions"), list)
        ):
            action_sources = [
                json.dumps(action)
                for action in structured["actions"]
            ]
            visible_response = ""
        else:
            action_sources = []

    except json.JSONDecodeError as error:
        return visible_response, [], [f"Ung?ltige JSON-Antwort: {error}"]

    for source in action_sources:
        try:
            action = json.loads(source)

            if not isinstance(action, dict):
                raise ValueError(
                    "Eine forgeai-action muss ein JSON-Objekt sein."
                )

            operation = action.get("operation")
            path = action.get("path")

            if operation not in {
                "create",
                "create_directory",
                "replace",
            }:
                raise ValueError(
                    "Nur 'create', 'create_directory' und 'replace' "
                    "sind für KI-Änderungen erlaubt."
                )

            if not isinstance(path, str) or not path.strip():
                raise ValueError(
                    "Jede forgeai-action benötigt einen gültigen "
                    "relativen Pfad."
                )

            if operation == "create":
                content = action.get("content", "")

                if not isinstance(content, str):
                    raise ValueError(
                        "Das Feld 'content' muss ein Text sein."
                    )

                previews.append(
                    workspace.create_file(
                        path,
                        content,
                    )
                )

            elif operation == "create_directory":
                previews.append(
                    workspace.create_directory(path)
                )

            elif operation == "replace":
                old = action.get("old")
                new = action.get("new")

                if old is None:
                    raise ValueError(
                        "Bei 'replace' fehlt das erforderliche Feld 'old'."
                    )

                if new is None:
                    raise ValueError(
                        "Bei 'replace' fehlt das erforderliche Feld 'new'."
                    )

                if not isinstance(old, str):
                    raise ValueError(
                        "Das Feld 'old' muss ein Text sein."
                    )

                if not isinstance(new, str):
                    raise ValueError(
                        "Das Feld 'new' muss ein Text sein."
                    )

                previews.append(
                    workspace.replace_text(
                        path,
                        old,
                        new,
                    )
                )

        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            FileExistsError, OSError,
        ) as error:
            errors.append(str(error))

    return visible_response, previews, errors
