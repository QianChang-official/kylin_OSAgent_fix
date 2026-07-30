"""Tests for the static security invariant analyzer.

The analyzer is what turns "we have a guardrail" into a checkable claim,
so it must itself be trustworthy: it has to pass on the real codebase AND
actually catch violations when they exist.
"""
import textwrap

import pytest

from backend.security.invariants import STATIC_INVARIANTS, analyze


@pytest.fixture()
def fake_project(tmp_path):
    """Build a minimal project tree the analyzer can walk."""
    def _build(files: dict[str, str]):
        backend = tmp_path / "backend"
        for rel, source in files.items():
            path = backend / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(source), encoding="utf-8")
        return tmp_path
    return _build


CLEAN_EXECUTOR = """
    import subprocess

    def run(command):
        return subprocess.run(command, shell=False, capture_output=True, timeout=10)
"""

CLEAN_TOOL = """
    from backend.executor import SafeExecutor

    _executor = SafeExecutor()

    def check():
        return _executor.run(["df", "-h"])
"""


# ---------- the real codebase must pass ----------

def test_real_backend_satisfies_all_static_invariants():
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    report = analyze(project_root)
    assert report.files_scanned > 0
    assert report.violations == [], [item.to_dict() for item in report.violations]
    assert report.passed is True


def test_real_backend_has_exactly_one_subprocess_owner():
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    report = analyze(project_root)
    owners = {site["file"] for site in report.subprocess_sites}
    assert owners == {"backend/executor/safe_executor.py"}


# ---------- the analyzer must catch violations ----------

def test_detects_subprocess_outside_executor(fake_project):
    root = fake_project({
        "executor/safe_executor.py": CLEAN_EXECUTOR,
        "tools/rogue.py": """
            import subprocess

            def check():
                return subprocess.run(["df"], shell=False)
        """,
    })
    report = analyze(root)
    codes = {item.invariant for item in report.violations}
    assert "INV-S1" in codes
    assert "INV-S4" in codes  # a tool module reaching the OS directly
    assert report.passed is False


def test_detects_shell_true(fake_project):
    root = fake_project({
        "executor/safe_executor.py": """
            import subprocess

            def run(command):
                return subprocess.run(command, shell=True)
        """,
    })
    report = analyze(root)
    codes = {item.invariant for item in report.violations}
    assert "INV-S2" in codes


def test_detects_os_system(fake_project):
    root = fake_project({
        "executor/safe_executor.py": CLEAN_EXECUTOR,
        "tools/bad.py": """
            import os

            def check():
                os.system("df -h")
        """,
    })
    report = analyze(root)
    assert "INV-S3" in {item.invariant for item in report.violations}


def test_detects_eval_and_exec(fake_project):
    root = fake_project({
        "executor/safe_executor.py": CLEAN_EXECUTOR,
        "bad_eval.py": """
            def run(payload):
                return eval(payload)
        """,
    })
    report = analyze(root)
    assert "INV-S3" in {item.invariant for item in report.violations}


def test_detects_missing_explicit_shell_false(fake_project):
    root = fake_project({
        "executor/safe_executor.py": """
            import subprocess

            def run(command):
                return subprocess.run(command, capture_output=True)
        """,
    })
    report = analyze(root)
    assert "INV-S5" in {item.invariant for item in report.violations}


def test_detects_os_access_spread_across_modules(fake_project):
    root = fake_project({
        "executor/safe_executor.py": CLEAN_EXECUTOR,
        "other/second_owner.py": """
            import subprocess

            def run(command):
                return subprocess.run(command, shell=False)
        """,
    })
    report = analyze(root)
    details = " ".join(item.detail for item in report.violations)
    assert "single-sourced" in details


def test_clean_project_passes(fake_project):
    root = fake_project({
        "executor/safe_executor.py": CLEAN_EXECUTOR,
        "tools/disk.py": CLEAN_TOOL,
    })
    report = analyze(root)
    assert report.passed is True
    assert len(report.subprocess_sites) == 1


def test_tests_directory_is_excluded_from_proof(fake_project):
    """Test fixtures legitimately contain unsafe-looking code."""
    root = fake_project({
        "executor/safe_executor.py": CLEAN_EXECUTOR,
        "tests/test_something.py": """
            import subprocess

            def test_x():
                subprocess.run(["echo"], shell=True)
        """,
    })
    report = analyze(root)
    assert report.passed is True


def test_missing_backend_dir_is_reported(tmp_path):
    report = analyze(tmp_path)
    assert report.passed is False


def test_every_declared_invariant_has_description():
    assert set(STATIC_INVARIANTS) == {"INV-S1", "INV-S2", "INV-S3", "INV-S4", "INV-S5"}
    assert all(text for text in STATIC_INVARIANTS.values())
