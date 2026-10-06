from __future__ import annotations

import pytest

from forgeai.core.capability_registry import (
    CapabilityRegistry,
    PluginCategory,
    PluginManifest,
    ResourceRequirements,
)


def test_registry_matches_task_hints_and_explicit_capabilities_without_touching_filesystem():
    registry = CapabilityRegistry()
    registry.register(
        PluginManifest(
            plugin_id="python",
            name="Python",
            version="1.0",
            category=PluginCategory.DEVELOPMENT,
            capabilities=("code.python", "test.python"),
            task_hints=("python", "pytest"),
            project_markers=("pyproject.toml",),
        )
    )

    matches = registry.match_request(
        "Bitte den Python Test reparieren",
        observed_project_markers=("pyproject.toml",),
    )

    assert len(matches) == 1
    assert matches[0].plugin_id == "python"
    assert "task_hint:python" in matches[0].reasons
    assert "project_marker:pyproject.toml" in matches[0].reasons
    assert matches[0].capability_ids == ("code.python", "test.python")


def test_explicit_capability_maps_only_to_declared_provider():
    registry = CapabilityRegistry()
    registry.register(
        PluginManifest(
            plugin_id="image",
            name="Image",
            version="1",
            capabilities=("image.generate",),
        )
    )
    registry.register(
        PluginManifest(
            plugin_id="video",
            name="Video",
            version="1",
            capabilities=("video.generate",),
        )
    )

    matches = registry.match_request("neutral", explicit_capabilities=("video.generate",))
    assert [item.plugin_id for item in matches] == ["video"]
    assert matches[0].capability_ids == ("video.generate",)


def test_manifest_rejects_self_dependency_and_duplicate_capabilities():
    with pytest.raises(ValueError):
        PluginManifest(
            plugin_id="x",
            name="X",
            version="1",
            dependencies=("x",),
        )

    with pytest.raises(ValueError):
        PluginManifest(
            plugin_id="x",
            name="X",
            version="1",
            capabilities=("a", "a"),
        )


def test_resource_requirements_reject_negative_values():
    with pytest.raises(ValueError):
        ResourceRequirements(min_vram_mb=-1)
