"""Tests for the static security invariant analyzer.

The analyzer is what turns "we have a guardrail" into a checkable claim,
so it must itself be trustworthy: it has to pass on the real codebase AND
actually catch violations when they exist.
"""
import importlib.util
import re
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

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


# ---------- the final-delivery manifest must fail closed ----------

PACKAGE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "package-final.py"


def _package_git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _package_write(project: Path, relative: str, content: str) -> Path:
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture()
def package_project(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("safeops_package_final", PACKAGE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    repository = tmp_path / "\u6d4b\u8bd5 repository"
    project = repository / "safeopsagent"
    project.mkdir(parents=True)
    _package_git(repository, "init", "--quiet")
    monkeypatch.setattr(module, "PROJECT_ROOT", project)
    return module, repository, project


def test_delivery_archive_uses_reviewed_worktree_manifest(package_project):
    module, repository, project = package_project
    readme = _package_write(project, "README.md", "indexed version\n")
    deleted = _package_write(
        project,
        "BACKEND/STATIC/CONSOLE/ASSETS/old.JS",
        "old bundle\n",
    )
    _package_write(project, "Data/audit.json", "runtime data\n")
    _package_write(project, "Output/probe.txt", "local output\n")
    _package_write(project, ".playwright-cli/state.json", "browser state\n")
    _package_write(project, ".ENV", "secret=value\n")
    _package_write(project, "SECRET.PEM", "secret key\n")
    _package_write(project, "tests/data/fixture.json", "test fixture\n")
    output = _package_write(project, "release.tar.gz", "old archive\n")
    checksum = _package_write(project, "release.tar.gz.sha256", "old checksum\n")
    _package_git(repository, "add", "-f", "--", "safeopsagent")

    readme.write_text("modified working copy\n", encoding="utf-8")
    deleted.unlink()
    _package_write(
        project,
        "BACKEND/STATIC/CONSOLE/ASSETS/app.JS",
        "console.log('new')\n",
    )
    _package_write(
        project,
        "BACKEND/STATIC/CONSOLE/ASSETS/app.CSS",
        "body { color: white; }\n",
    )
    _package_write(project, "BACKEND/TESTS/CONFTEST.PY", "VALUE = 'approved'\n")

    kept, skipped = module.build_archive(output)
    module.write_checksum(output)

    assert kept == 5
    assert skipped == 8
    with tarfile.open(output, "r:gz") as archive:
        names = set(archive.getnames())
        assert names == {
            "safeopsagent/README.md",
            "safeopsagent/BACKEND/STATIC/CONSOLE/ASSETS/app.JS",
            "safeopsagent/BACKEND/STATIC/CONSOLE/ASSETS/app.CSS",
            "safeopsagent/BACKEND/TESTS/CONFTEST.PY",
            "safeopsagent/tests/data/fixture.json",
        }
        extracted = archive.extractfile("safeopsagent/README.md")
        assert extracted is not None
        assert extracted.read() == readme.read_bytes()
    assert checksum.exists()
    assert re.fullmatch(rb"[0-9a-f]{64}  release\.tar\.gz\n", checksum.read_bytes())


def test_delivery_archive_rejects_unknown_untracked_without_overwrite(
    package_project,
    monkeypatch,
    capsys,
):
    module, repository, project = package_project
    _package_write(project, "README.md", "tracked\n")
    _package_git(repository, "add", "--", "safeopsagent")
    _package_write(project, "backend/static/console/assets/approved.js", "approved\n")
    _package_write(project, "backend/static/console/assets/source.js.map", "blocked\n")
    _package_write(project, "backend/static/console/assets/nested/bad.js", "blocked\n")
    _package_write(project, "notes.txt", "blocked\n")
    output = _package_write(project, "delivery.tar.gz", "previous delivery\n")
    checksum = _package_write(project, "delivery.tar.gz.sha256", "previous checksum\n")
    monkeypatch.setattr(sys, "argv", [str(PACKAGE_SCRIPT), "-o", str(output)])

    assert module.main() == 1
    captured = capsys.readouterr()
    assert "Refusing to package unapproved untracked files" in captured.err
    assert "source.js.map" in captured.err
    assert "nested/bad.js" in captured.err
    assert "notes.txt" in captured.err
    assert "approved.js" not in captured.err
    assert output.read_text(encoding="utf-8") == "previous delivery\n"
    assert checksum.read_text(encoding="utf-8") == "previous checksum\n"


def test_delivery_archive_rejects_missing_tracked_source(package_project):
    module, repository, project = package_project
    missing = _package_write(project, "README.md", "tracked\n")
    output = _package_write(project, "delivery.tar.gz", "previous delivery\n")
    _package_git(repository, "add", "--", "safeopsagent")
    missing.unlink()

    with pytest.raises(module.PackagingError, match=r"missing tracked file: README\.md"):
        module.build_archive(output)

    assert output.read_text(encoding="utf-8") == "previous delivery\n"


def test_delivery_archive_rejects_tracked_symlink(package_project, monkeypatch):
    module, repository, project = package_project
    linked = _package_write(project, "backend/static/console/assets/linked.js", "tracked\n")
    output = _package_write(project, "delivery.tar.gz", "previous delivery\n")
    _package_git(repository, "add", "--", "safeopsagent")
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == linked or real_is_symlink(path),
    )

    with pytest.raises(module.PackagingError, match=r"symlink: .*linked\.js"):
        module.build_archive(output)

    assert output.read_text(encoding="utf-8") == "previous delivery\n"
