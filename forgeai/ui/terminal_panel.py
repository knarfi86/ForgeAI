import subprocess

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class TerminalPanel(QWidget):
    def __init__(self):
        super().__init__(); layout = QVBoxLayout(self)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True)
        row = QHBoxLayout(); self.command = QLineEdit(); self.command.setPlaceholderText("PowerShell-Befehl ausführen …")
        run = QPushButton("Ausführen"); run.clicked.connect(self.run_command); self.command.returnPressed.connect(self.run_command)
        row.addWidget(self.command, 1); row.addWidget(run); layout.addWidget(self.output, 1); layout.addLayout(row)
        self.process = QProcess(self); self.process.readyReadStandardOutput.connect(self._read_stdout); self.process.readyReadStandardError.connect(self._read_stderr)

    def set_working_directory(self, path: str) -> None:
        """Run subsequent terminal commands from the active project."""
        self.process.setWorkingDirectory(path)

    def run_command(self):
        command = self.command.text().strip()
        if command and self.process.state() == QProcess.NotRunning:
            self.output.appendPlainText(f"> {command}"); self.command.clear()
            self.process.start("powershell.exe", ["-NoProfile", "-Command", command])

    def _read_stdout(self): self.output.appendPlainText(bytes(self.process.readAllStandardOutput()).decode(errors="replace"))
    def _read_stderr(self): self.output.appendPlainText(bytes(self.process.readAllStandardError()).decode(errors="replace"))
