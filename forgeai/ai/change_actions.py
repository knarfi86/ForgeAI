"""Translate explicitly marked model actions into safe workspace previews."""

import json
import re

from forgeai.core.workspace_tools import ChangePreview, WorkspaceTools


ACTION_BLOCK = re.compile(r"```forgeai-action\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_change_previews(response: str, workspace: WorkspaceTools) -> tuple[str, list[ChangePreview], list[str]]:
    """Remove action blocks from a response and turn valid ones into previews."""
    previews: list[ChangePreview] = []
    errors: list[str] = []
    for match in ACTION_BLOCK.finditer(response):
        try:
            action = json.loads(match.group(1))
            operation = action["operation"]
            if operation == "create":
                previews.append(workspace.create_file(action["path"], action.get("content", "")))
            elif operation == "replace":
                previews.append(workspace.replace_text(action["path"], action["old"], action["new"]))
            else:
                raise ValueError("Nur 'create' und 'replace' sind für KI-Änderungen erlaubt.")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, FileExistsError) as error:
            errors.append(str(error))
    return ACTION_BLOCK.sub("", response).strip(), previews, errors
