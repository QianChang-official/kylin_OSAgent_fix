#!/usr/bin/env python3
"""Create a clean final delivery archive with a top-level safeopsagent/ dir."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import tarfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOP_DIR = "safeopsagent"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".venv-frontend",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "htmlcov",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite3",
    ".log",
    ".tmp",
    ".key",
    ".pem",
}

EXCLUDED_NAMES = {
    ".env",
    ".DS_Store",
    ".coverage",
    "coverage.xml",
    "audit.db",
}


def get_version_tag() -> str:
    """Git short hash when available, else the app version (e.g. v1.3.0)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        short_hash = result.stdout.strip()
        if short_hash:
            return short_hash
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # No git metadata (e.g. packaging from an extracted archive): fall back to
    # the version declared in backend/app.py so the filename stays meaningful.
    app_file = PROJECT_ROOT / "backend" / "app.py"
    try:
        for line in app_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("APP_VERSION"):
                return "v" + line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "final"


def default_archive_path() -> Path:
    return PROJECT_ROOT.parent / f"safeopsagent-{get_version_tag()}-final-delivery.tar.gz"


def should_exclude(path: Path) -> bool:
    rel = path.relative_to(PROJECT_ROOT)
    parts = set(rel.parts)
    if parts & EXCLUDED_DIRS:
        return True

    # Runtime audit data must not be packaged, but tests/data fixtures stay.
    if rel.parts and rel.parts[0] == "data":
        return True

    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.match("safeopsagent-*.tar.gz"):
        return True
    return False


def build_archive_with_git(output: Path) -> bool:
    if not (PROJECT_ROOT / ".git").exists():
        return False
    output = output.resolve()
    if output.exists():
        output.unlink()
    try:
        subprocess.run(
            [
                "git",
                "archive",
                "--format=tar.gz",
                f"--prefix={TOP_DIR}/",
                "-o",
                str(output),
                "HEAD",
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


def build_archive(output: Path) -> tuple[int, int]:
    output = output.resolve()
    kept = 0
    skipped = 0
    if output.exists():
        output.unlink()

    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(PROJECT_ROOT.rglob("*")):
            if path == output or output in path.parents:
                skipped += 1
                continue
            if should_exclude(path):
                skipped += 1
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(PROJECT_ROOT)
            archive.add(path, arcname=str(Path(TOP_DIR) / rel))
            kept += 1
    return kept, skipped


def write_checksum(archive: Path) -> Path:
    """Write the SHA256 next to the archive, as the delivery checklist requires."""
    digest = hashlib.sha256()
    with archive.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    checksum_path = archive.with_name(archive.name + ".sha256")
    # Force LF so `sha256sum -c` works when the package is built on Windows.
    with checksum_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{digest.hexdigest()}  {archive.name}\n")
    return checksum_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Package SafeOpsAgent final delivery archive.")
    parser.add_argument(
        "-o",
        "--output",
        default=str(default_archive_path()),
        help="Output .tar.gz path. Defaults to the parent directory of the project.",
    )
    args = parser.parse_args()
    output = Path(args.output)
    if build_archive_with_git(output):
        kept, skipped = -1, -1
        method = "git archive"
    else:
        kept, skipped = build_archive(output)
        method = "python tarfile fallback"
    checksum_path = write_checksum(output.resolve())
    print(f"archive={output}")
    print(f"top_dir={TOP_DIR}/")
    print(f"method={method}")
    if kept >= 0:
        print(f"files_kept={kept}")
        print(f"items_skipped={skipped}")
    print(f"size_bytes={output.resolve().stat().st_size}")
    print(f"checksum={checksum_path}")
    print(f"sha256={checksum_path.read_text(encoding='utf-8').split()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
