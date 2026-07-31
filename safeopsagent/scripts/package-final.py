#!/usr/bin/env python3
"""Create a clean final delivery archive with a top-level safeopsagent/ dir."""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

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
    ".playwright-cli",
    "node_modules",
    "output",
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

ALLOWED_UNTRACKED_ASSET_DIR = Path("backend/static/console/assets")
ALLOWED_UNTRACKED_FILE = Path("backend/tests/conftest.py")


class PackagingError(RuntimeError):
    """Raised when the delivery file set cannot be established safely."""


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
    # the version declared in backend/__init__.py so the filename stays
    # meaningful. Parsed textually rather than imported, because packaging
    # must work without the backend's runtime dependencies installed.
    init_file = PROJECT_ROOT / "backend" / "__init__.py"
    try:
        for line in init_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                return "v" + line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "final"


def default_archive_path() -> Path:
    return PROJECT_ROOT.parent / f"safeopsagent-{get_version_tag()}-final-delivery.tar.gz"


def should_exclude(path: Path) -> bool:
    rel = path.relative_to(PROJECT_ROOT)
    parts = {part.casefold() for part in rel.parts}
    if parts & EXCLUDED_DIRS:
        return True

    # Runtime audit data must not be packaged, but tests/data fixtures stay.
    if rel.parts and rel.parts[0].casefold() == "data":
        return True

    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return True
    if path.name.casefold() in {name.casefold() for name in EXCLUDED_NAMES}:
        return True
    lower_name = path.name.casefold()
    if lower_name.startswith("safeopsagent-") and lower_name.endswith(".tar.gz"):
        return True
    return False


def git_project_context() -> tuple[Path, PurePosixPath]:
    try:
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
        git_root = Path(os.fsdecode(root_result.stdout.rstrip(b"\r\n"))).resolve()
        project_relative = PurePosixPath(PROJECT_ROOT.resolve().relative_to(git_root).as_posix())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        raise PackagingError("SafeOpsAgent must be packaged from a Git working tree") from exc
    return git_root, project_relative


def git_file_list(
    git_root: Path,
    project_relative: PurePosixPath,
    *options: str,
) -> list[Path]:
    project_pathspec = project_relative.as_posix() if project_relative.parts else "."
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", *options, "--", project_pathspec],
            cwd=git_root,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise PackagingError("Unable to read the Git delivery file list") from exc

    project_files: list[Path] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        repository_path = PurePosixPath(os.fsdecode(raw_path))
        try:
            relative = (
                repository_path.relative_to(project_relative)
                if project_relative.parts
                else repository_path
            )
        except ValueError as exc:
            raise PackagingError(f"Git returned a path outside the project: {repository_path}") from exc
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise PackagingError(f"Git returned an invalid project path: {repository_path}")
        project_files.append(Path(*relative.parts))
    return sorted(set(project_files), key=lambda path: path.as_posix())


def allowed_untracked(path: Path) -> bool:
    normalized = path.as_posix().casefold()
    if normalized == ALLOWED_UNTRACKED_FILE.as_posix().casefold():
        return True
    return (
        path.parent.as_posix().casefold() == ALLOWED_UNTRACKED_ASSET_DIR.as_posix().casefold()
        and path.suffix.casefold() in {".js", ".css"}
    )


def allowed_deleted_tracked(path: Path) -> bool:
    return (
        path.parent.as_posix().casefold() == ALLOWED_UNTRACKED_ASSET_DIR.as_posix().casefold()
        and path.suffix.casefold() in {".js", ".css"}
    )


def is_output_artifact(path: Path, output: Path) -> bool:
    resolved = path.resolve(strict=False)
    output = output.resolve(strict=False)
    checksum = output.with_name(output.name + ".sha256")
    return resolved in {output, checksum}


def delivery_files(output: Path) -> tuple[list[Path], int]:
    git_root, project_relative = git_project_context()
    tracked = git_file_list(git_root, project_relative, "--cached")
    untracked = git_file_list(git_root, project_relative, "--others", "--exclude-standard")

    approved_untracked: list[Path] = []
    unexpected_untracked: list[Path] = []
    for relative in untracked:
        path = PROJECT_ROOT / relative
        if is_output_artifact(path, output):
            continue
        if allowed_untracked(relative):
            approved_untracked.append(relative)
        else:
            unexpected_untracked.append(relative)

    if unexpected_untracked:
        listed = "\n".join(f"  - {path.as_posix()}" for path in unexpected_untracked)
        raise PackagingError(
            "Refusing to package unapproved untracked files:\n" + listed
        )

    tracked_set = set(tracked)
    kept: list[Path] = []
    invalid_paths: list[str] = []
    skipped = 0
    for relative in sorted(set(tracked + approved_untracked), key=lambda path: path.as_posix()):
        path = PROJECT_ROOT / relative
        if path.is_symlink():
            invalid_paths.append(f"symlink: {relative.as_posix()}")
            continue
        if is_output_artifact(path, output):
            skipped += 1
            continue
        if not path.exists():
            if relative in tracked_set and not allowed_deleted_tracked(relative):
                invalid_paths.append(f"missing tracked file: {relative.as_posix()}")
                continue
            skipped += 1
            continue
        if not path.is_file():
            invalid_paths.append(f"non-regular file: {relative.as_posix()}")
            continue
        if should_exclude(path):
            skipped += 1
            continue
        kept.append(relative)

    if invalid_paths:
        listed = "\n".join(f"  - {item}" for item in invalid_paths)
        raise PackagingError("Refusing to package invalid working-tree paths:\n" + listed)
    return kept, skipped


def build_archive(output: Path) -> tuple[int, int]:
    output = output.resolve()
    files, skipped = delivery_files(output)
    if output.exists():
        output.unlink()

    with tarfile.open(output, "w:gz") as archive:
        for relative in files:
            path = PROJECT_ROOT / relative
            arcname = (PurePosixPath(TOP_DIR) / PurePosixPath(relative.as_posix())).as_posix()
            archive.add(path, arcname=arcname)
    return len(files), skipped


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
    try:
        kept, skipped = build_archive(output)
    except PackagingError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    method = "git-index working copy"
    checksum_path = write_checksum(output.resolve())
    print(f"archive={output}")
    print(f"top_dir={TOP_DIR}/")
    print(f"method={method}")
    print(f"files_kept={kept}")
    print(f"items_skipped={skipped}")
    print(f"size_bytes={output.resolve().stat().st_size}")
    print(f"checksum={checksum_path}")
    print(f"sha256={checksum_path.read_text(encoding='utf-8').split()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
