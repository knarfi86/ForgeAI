"""Translate explicitly marked model actions into safe workspace previews."""

import json
import re

from forgeai.core.workspace_tools import ChangePreview, WorkspaceTools


ACTION_BLOCK = re.compile(r"```forgeai-action\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_change_previews(response: str, workspace: WorkspaceTools) -> tuple[str, list[ChangePreview], list[str]]:
    """Remove action blocks from a response and turn valid ones into previews."""
    previews: list[ChangePreview] = []
    errors: list[str] = []
    action_sources = [match.group(1) for match in ACTION_BLOCK.finditer(response)]
    visible_response = ACTION_BLOCK.sub("", response).strip()
    if not action_sources:
        try:
            structured = json.loads(response)
            if isinstance(structured, dict) and isinstance(structured.get("actions"), list):
                action_sources = [json.dumps(action) for action in structured["actions"]]
                visible_response = ""
        except json.JSONDecodeError:
            pass
    for source in action_sources:
        try:
            action = json.loads(source)
            operation = action["operation"]
            if operation == "create":
                previews.append(workspace.create_file(action["path"], action.get("content", "")))
            elif operation == "create_directory":
                previews.append(workspace.create_directory(action["path"]))
            elif operation == "replace":
                previews.append(workspace.replace_text(action["path"], action["old"], action["new"]))
            else:
                raise ValueError("Nur 'create', 'create_directory' und 'replace' sind für KI-Änderungen erlaubt.")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, FileExistsError) as error:
            errors.append(str(error))
    return visible_response, previews, errors
