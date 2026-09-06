from pathlib import Path

from forgeai.core.test_runner import ProjectTestRunner


def test_detects_powershell_runner(tmp_path):
    script = tmp_path / "scripts" / "run_tests.ps1"
    script.parent.mkdir()
    script.write_text("Write-Host test", encoding="utf-8")

    name, command = ProjectTestRunner(tmp_path)._detect()

    assert name == "powershell"
    assert command[-1] == str(script)


def test_detects_pytest_for_python_project(tmp_path, monkeypatch):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "def test_sample():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ProjectTestRunner,
        "_python_has_pytest",
        staticmethod(lambda python: True),
    )

    name, command = ProjectTestRunner(tmp_path)._detect()

    assert name == "pytest"
    assert command[-3:] == ["-m", "pytest", "-q"]


def test_falls_back_to_unittest(tmp_path, monkeypatch):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "import unittest\n\n"
        "class TestSample(unittest.TestCase):\n"
        "    def test_sample(self):\n"
        "        self.assertTrue(True)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        ProjectTestRunner,
        "_python_has_pytest",
        staticmethod(lambda python: False),
    )

    name, command = ProjectTestRunner(tmp_path)._detect()

    assert name == "unittest"
    assert command[-4:] == ["unittest", "discover", "-s", "tests"]
