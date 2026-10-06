from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from forgeai.core.plugin_manager import CapabilityExecutionContext, PluginManager


class CapabilitiesDialog(QDialog):
    """Control center for optional Forge capability plugins."""

    def __init__(
        self,
        manager: PluginManager,
        *,
        project_path: str | Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.project_path = str(Path(project_path)) if project_path else None
        self._rows: dict[str, tuple[QCheckBox, QCheckBox, QCheckBox | None]] = {}

        self.setWindowTitle("Plugins & Fähigkeiten")
        self.resize(980, 520)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Forge wählt benötigte Fähigkeiten innerhalb deiner Freigaben automatisch aus. "
            "Aktivieren bedeutet verfügbar; autonome Nutzung erlaubt Forge die selbstständige Auswahl. "
            "Die Ausführung erfolgt zunächst strikt nacheinander."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if self.project_path:
            project_label = QLabel(f"Aktuelles Projekt: {self.project_path}")
            project_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(project_label)

        manifests = self.manager.registry.list_manifests()
        if not manifests:
            empty = QLabel(
                "Noch keine Spezialplugins registriert. Das Plugin-Grundgerüst ist aktiv; "
                "als erstes Referenzplugin ist Python vorgesehen."
            )
            empty.setWordWrap(True)
            layout.addWidget(empty)
            self.table = None
        else:
            columns = [
                "Plugin",
                "Kategorie",
                "Status",
                "Aktiviert",
                "Autonom",
            ]
            if self.project_path:
                columns.append("Projekt-Auto")
            columns.extend(["Fähigkeiten", "Prüfprofile", "Ressourcen"])

            table = QTableWidget(len(manifests), len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

            for row, manifest in enumerate(manifests):
                prefs = self.manager.preferences(manifest.plugin_id)

                name_item = QTableWidgetItem(f"{manifest.name}  ({manifest.version})")
                name_item.setToolTip(manifest.description or manifest.plugin_id)
                table.setItem(row, 0, name_item)
                table.setItem(row, 1, QTableWidgetItem(manifest.category.value))

                try:
                    availability = self.manager.evaluate_availability(
                        manifest.plugin_id,
                        CapabilityExecutionContext(
                            task_id="ui-capability-status",
                            execution_round=0,
                            project_path=self.project_path,
                        ),
                    )
                    status_text = "Bereit" if availability.available else "Nicht verfügbar"
                    status_item = QTableWidgetItem(status_text)
                    details = list(availability.details)
                    if availability.reason_codes:
                        details.extend(availability.reason_codes)
                    if details:
                        status_item.setToolTip("\n".join(details))
                except Exception as error:
                    status_item = QTableWidgetItem("Prüfung fehlgeschlagen")
                    status_item.setToolTip(str(error))
                table.setItem(row, 2, status_item)

                enabled = QCheckBox()
                enabled.setChecked(prefs.enabled)
                table.setCellWidget(row, 3, enabled)

                autonomous = QCheckBox()
                autonomous.setChecked(prefs.autonomous)
                table.setCellWidget(row, 4, autonomous)

                project_auto: QCheckBox | None = None
                offset = 5
                if self.project_path:
                    project_auto = QCheckBox()
                    project_auto.setChecked(prefs.autonomous_for(self.project_path))
                    project_auto.setToolTip(
                        "Erlaubt Forge die autonome Nutzung dieses Plugins im aktuellen Projekt."
                    )
                    table.setCellWidget(row, 5, project_auto)
                    offset = 6

                table.setItem(row, offset, QTableWidgetItem(", ".join(manifest.capabilities) or "–"))
                table.setItem(
                    row,
                    offset + 1,
                    QTableWidgetItem(", ".join(manifest.verification_profiles) or "–"),
                )
                resource_parts: list[str] = []
                if manifest.resources.gpu_required:
                    resource_parts.append("GPU")
                if manifest.resources.min_vram_mb:
                    resource_parts.append(f"VRAM ≥ {manifest.resources.min_vram_mb} MB")
                if manifest.resources.min_ram_mb:
                    resource_parts.append(f"RAM ≥ {manifest.resources.min_ram_mb} MB")
                resource_parts.extend(manifest.resources.exclusive_resources)
                table.setItem(row, offset + 2, QTableWidgetItem(", ".join(resource_parts) or "CPU/normal"))

                self._rows[manifest.plugin_id] = (enabled, autonomous, project_auto)

            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setStretchLastSection(True)
            layout.addWidget(table, 1)
            self.table = table

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_preferences(self) -> None:
        for plugin_id, (enabled, autonomous, project_auto) in self._rows.items():
            self.manager.set_enabled(plugin_id, enabled.isChecked())
            self.manager.set_autonomous(plugin_id, autonomous.isChecked())
            if self.project_path and project_auto is not None:
                self.manager.set_project_autonomous(
                    plugin_id,
                    self.project_path,
                    project_auto.isChecked(),
                )
