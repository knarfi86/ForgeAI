"""Translate explicitly marked model actions into safe workspace previews."""

import json
import re

from forgeai.core.workspace_tools import ChangePreview, WorkspaceTools


ACTION_BLOCK = re.compile(
    r"`forgeai-action\s*\n(.*?)`",
    re.DOTALL | re.IGNORECASE,
)


def extract_change_previews(
    response: str,
    workspace: WorkspaceTools,
) -> tuple[str, list[ChangePreview], list[str]]:
    """Remove action blocks from a response and turn valid ones into previews."""

    previews: list[ChangePreview] = []
    errors: list[str] = []

    action_sources = [
        match.group(1)
        for match in ACTION_BLOCK.finditer(response)
    ]

    visible_response = ACTION_BLOCK.sub("", response).strip()

    if not action_sources:
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

        except json.JSONDecodeError:
            pass

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
                    "sind fÃ¼r KI-Ã„nderungen erlaubt."
                )

            if not isinstance(path, str) or not path.strip():
                raise ValueError(
                    "Jede forgeai-action benÃ¶tigt einen gÃ¼ltigen "
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
