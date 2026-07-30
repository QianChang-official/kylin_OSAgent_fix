"""Strictly scoped, reversible cleanup operations.

Only regular, single-link files under configured temporary roots can become
candidates. Quarantine uses same-filesystem atomic moves and never deletes.
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import re
import stat
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from backend import config


QUARANTINE_DIR_NAME = ".safeopsagent-quarantine"
PLAN_ID_RE = re.compile(r"^[a-f0-9]{32}$")
FORBIDDEN_CLEANUP_ROOTS = {
    "/",
    "/boot",
    "/dev",
    "/etc",
    "/home",
    "/proc",
    "/root",
    "/sys",
    "/usr",
    "/var",
}


class CleanupError(RuntimeError):
    """A safe, user-facing refusal from the cleanup subsystem."""


class CleanupService:
    def __init__(
        self,
        *,
        allowed_roots: tuple[str | Path, ...] | None = None,
        now_fn=None,
    ):
        roots = allowed_roots if allowed_roots is not None else config.SAFE_CLEANUP_ALLOWED_ROOTS
        resolved_roots = (
            Path(root).expanduser().resolve(strict=False)
            for root in roots
        )
        self.allowed_roots = tuple(
            root for root in resolved_roots if not self._is_forbidden_cleanup_root(root)
        )
        self.now_fn = now_fn or time.time
        self._plans: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def scan(
        self,
        path: str = "/tmp",
        min_age_hours: int = config.SAFE_CLEANUP_MIN_AGE_HOURS,
        max_files: int = config.SAFE_CLEANUP_MAX_FILES,
    ) -> dict[str, Any]:
        root = self._validate_requested_root(path)
        min_age_hours = self._bounded_int(min_age_hours, 1, 24 * 365, "min_age_hours")
        max_files = self._bounded_int(max_files, 1, config.SAFE_CLEANUP_MAX_FILES, "max_files")
        cutoff = self.now_fn() - min_age_hours * 3600
        candidates: list[dict[str, Any]] = []
        warnings: list[str] = []
        scanned_files = 0
        total_bytes = 0

        def onerror(exc: OSError) -> None:
            self._warning(warnings, f"Skipped {getattr(exc, 'filename', 'unknown')}: {exc}")

        for current, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
            current_path = Path(current)
            dirs[:] = self._safe_directories(root, current_path, dirs, warnings)
            for name in files:
                if scanned_files >= config.SAFE_CLEANUP_MAX_SCAN_FILES:
                    self._warning(
                        warnings,
                        f"Reached scan limit {config.SAFE_CLEANUP_MAX_SCAN_FILES}",
                    )
                    break
                scanned_files += 1
                candidate_path = current_path / name
                try:
                    candidate = self._candidate(root, candidate_path, cutoff)
                except CleanupError as exc:
                    self._warning(warnings, str(exc))
                    continue
                if candidate is None:
                    continue
                if candidate["bytes"] > config.SAFE_CLEANUP_MAX_FILE_BYTES:
                    self._warning(warnings, f"Skipped oversized file: {candidate_path}")
                    continue
                if total_bytes + candidate["bytes"] > config.SAFE_CLEANUP_MAX_TOTAL_BYTES:
                    self._warning(warnings, "Reached cleanup total-size safety limit")
                    break
                candidates.append(candidate)
                total_bytes += candidate["bytes"]
                if len(candidates) >= max_files:
                    break
            if (
                len(candidates) >= max_files
                or scanned_files >= config.SAFE_CLEANUP_MAX_SCAN_FILES
                or total_bytes >= config.SAFE_CLEANUP_MAX_TOTAL_BYTES
            ):
                break

        candidates.sort(key=lambda item: (item["modified_at_epoch"], item["path"]))
        return {
            "root": str(root),
            "min_age_hours": min_age_hours,
            "candidate_count": len(candidates),
            "total_bytes": total_bytes,
            "scanned_files": scanned_files,
            "candidates": candidates,
            "warnings": warnings,
            "dry_run": True,
            "permanent_delete": False,
        }

    def create_plan(
        self,
        path: str = "/tmp",
        min_age_hours: int = config.SAFE_CLEANUP_MIN_AGE_HOURS,
        max_files: int = config.SAFE_CLEANUP_MAX_FILES,
    ) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired_plans()
            scan = self.scan(path, min_age_hours, max_files)
            plan_id = uuid.uuid4().hex
            created_at = self.now_fn()
            immutable = {
                "plan_id": plan_id,
                "root": scan["root"],
                "min_age_hours": scan["min_age_hours"],
                "candidates": scan["candidates"],
                "total_bytes": scan["total_bytes"],
                "created_at": created_at,
            }
            plan_hash = self._digest(immutable)
            record = {
                **immutable,
                "plan_hash": plan_hash,
                "expires_at": created_at + config.SAFE_CLEANUP_PLAN_TTL_SECONDS,
                "used": False,
            }
            self._plans[plan_id] = record
            return {
                "plan_id": plan_id,
                "plan_hash": plan_hash,
                "root": scan["root"],
                "candidate_count": scan["candidate_count"],
                "total_bytes": scan["total_bytes"],
                "candidates": scan["candidates"],
                "warnings": scan["warnings"],
                "created_at": created_at,
                "expires_at": record["expires_at"],
                "dry_run": True,
                "executed": False,
                "message": "该操作需要人工确认，尚未执行。",
            }

    def quarantine(self, plan_id: str, plan_hash: str) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired_plans(exclude_plan_id=plan_id)
            plan = self._plans.get(plan_id)
            if not plan:
                raise CleanupError("Cleanup plan not found or expired")
            if plan.get("used"):
                raise CleanupError("Cleanup plan has already been used")
            if not self._constant_equal(str(plan.get("plan_hash", "")), str(plan_hash)):
                raise CleanupError("Cleanup plan hash does not match")
            if plan.get("expires_at", 0) < self.now_fn():
                self._plans.pop(plan_id, None)
                raise CleanupError("Cleanup plan has expired")
            if not plan.get("candidates"):
                raise CleanupError("Cleanup plan has no candidate files")

            # Consume before filesystem mutation so failures cannot be replayed.
            plan["used"] = True
            plan["used_at"] = self.now_fn()
            root = self._validate_requested_root(str(plan["root"]))
            allowed_root = self._allowed_root_for(root)
            verified = [
                self._verify_candidate(root, candidate)
                for candidate in plan.get("candidates", [])
            ]
            quarantine_id = uuid.uuid4().hex
            quarantine_root = allowed_root / QUARANTINE_DIR_NAME / quarantine_id
            quarantine_parent = quarantine_root.parent
            quarantine_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._ensure_controlled_directory(quarantine_parent)
            if allowed_root.stat().st_dev != quarantine_parent.stat().st_dev:
                raise CleanupError("Cross-filesystem quarantine is not allowed")
            quarantine_root.mkdir(mode=0o700)
            self._ensure_controlled_directory(quarantine_root)

            moved: list[dict[str, Any]] = []
            try:
                for index, (candidate, source_stat) in enumerate(verified, start=1):
                    source = Path(candidate["path"])
                    self._verify_candidate(root, candidate)
                    destination = quarantine_root / self._quarantine_name(index, source.name)
                    if destination.exists() or destination.is_symlink():
                        raise CleanupError("Quarantine destination already exists")
                    os.replace(source, destination)
                    moved_item = {
                        "original_path": str(source),
                        "quarantine_path": str(destination),
                        "bytes": source_stat.st_size,
                        "inode": source_stat.st_ino,
                        "device": source_stat.st_dev,
                        "mtime_ns": source_stat.st_mtime_ns,
                    }
                    # Track before the post-move check so a raced entry is
                    # included in rollback even when its identity changed.
                    moved.append(moved_item)
                    destination_stat = self._safe_lstat(destination)
                    self._match_snapshot(destination_stat, candidate)
                    if destination_stat.st_nlink != 1:
                        raise CleanupError("Quarantined file link count changed")
            except Exception as exc:
                rollback_errors = self._rollback_quarantine(moved)
                message = f"Quarantine refused: {exc}"
                if rollback_errors:
                    message += f"; rollback requires review: {rollback_errors}"
                raise CleanupError(message) from exc

            manifest_core = {
                "quarantine_id": quarantine_id,
                "plan_id": plan_id,
                "plan_hash": plan_hash,
                "root": str(root),
                "created_at": self.now_fn(),
                "items": moved,
            }
            manifest_hash = self._digest(manifest_core)
            manifest = {
                **manifest_core,
                "manifest_hash": manifest_hash,
                "state": "quarantined",
                "updated_at": self.now_fn(),
            }
            try:
                self._write_manifest(quarantine_root, manifest)
            except Exception as exc:
                rollback_errors = self._rollback_quarantine(moved)
                message = f"Quarantine manifest could not be saved: {exc}"
                if rollback_errors:
                    message += f"; rollback requires review: {rollback_errors}"
                raise CleanupError(message) from exc
            return {
                "quarantine_id": quarantine_id,
                "manifest_hash": manifest_hash,
                "root": str(root),
                "moved_count": len(moved),
                "total_bytes": sum(item["bytes"] for item in moved),
                "items": moved,
                "permanent_delete": False,
                "restore_available": True,
            }

    def restore(self, quarantine_id: str, manifest_hash: str) -> dict[str, Any]:
        with self._lock:
            if not PLAN_ID_RE.fullmatch(str(quarantine_id or "")):
                raise CleanupError("Invalid quarantine identifier")
            quarantine_root, manifest = self._load_manifest(quarantine_id)
            if manifest.get("state") != "quarantined":
                raise CleanupError("Quarantine has already been restored or is unavailable")
            if not self._constant_equal(str(manifest.get("manifest_hash", "")), str(manifest_hash)):
                raise CleanupError("Quarantine manifest hash does not match")
            immutable = {
                key: manifest.get(key)
                for key in ("quarantine_id", "plan_id", "plan_hash", "root", "created_at", "items")
            }
            if not self._constant_equal(self._digest(immutable), str(manifest_hash)):
                raise CleanupError("Quarantine manifest integrity check failed")

            root = self._validate_requested_root(str(manifest.get("root", "")))
            verified: list[tuple[dict[str, Any], Path, Path]] = []
            for item in manifest.get("items", []):
                if not isinstance(item, dict):
                    raise CleanupError("Quarantine manifest contains an invalid item")
                source = Path(str(item.get("quarantine_path", "")))
                destination = Path(str(item.get("original_path", "")))
                if not self._is_within(source.resolve(strict=False), quarantine_root):
                    raise CleanupError("Quarantine item escaped the controlled directory")
                self._validate_destination(root, destination)
                if destination.exists() or destination.is_symlink():
                    raise CleanupError(f"Restore target already exists: {destination}")
                source_stat = self._safe_lstat(source)
                self._match_snapshot(source_stat, item)
                verified.append((item, source, destination))

            restored: list[dict[str, Any]] = []
            try:
                for item, source, destination in verified:
                    self._validate_destination(root, destination)
                    source_stat = self._safe_lstat(source)
                    self._match_snapshot(source_stat, item)
                    os.replace(source, destination)
                    restored_item = {
                        "original_path": str(destination),
                        "quarantine_path": str(source),
                        "bytes": item.get("bytes", 0),
                    }
                    restored.append(restored_item)
                    self._validate_destination(root, destination)
                    destination_stat = self._safe_lstat(destination)
                    self._match_snapshot(destination_stat, item)
                    if destination_stat.st_nlink != 1:
                        raise CleanupError("Restored file link count changed")
            except Exception as exc:
                rollback_errors = self._rollback_restore(restored)
                message = f"Restore refused: {exc}"
                if rollback_errors:
                    message += f"; rollback requires review: {rollback_errors}"
                raise CleanupError(message) from exc

            manifest["state"] = "restored"
            manifest["restored_at"] = self.now_fn()
            manifest["updated_at"] = self.now_fn()
            try:
                self._write_manifest(quarantine_root, manifest)
            except Exception as exc:
                rollback_errors = self._rollback_restore(restored)
                message = f"Restore manifest could not be saved: {exc}"
                if rollback_errors:
                    message += f"; rollback requires review: {rollback_errors}"
                raise CleanupError(message) from exc
            return {
                "quarantine_id": quarantine_id,
                "manifest_hash": manifest_hash,
                "restored_count": len(restored),
                "items": restored,
                "permanent_delete": False,
            }

    def _candidate(self, root: Path, path: Path, cutoff: float) -> dict[str, Any] | None:
        if path.suffix.lower() not in config.SAFE_CLEANUP_ALLOWED_SUFFIXES:
            return None
        self._ensure_path_components(root, path.parent)
        file_stat = self._safe_lstat(path)
        if not stat.S_ISREG(file_stat.st_mode):
            return None
        if file_stat.st_nlink != 1:
            raise CleanupError(f"Skipped hard-linked file: {path}")
        if hasattr(os, "geteuid") and file_stat.st_uid != os.geteuid():
            raise CleanupError(f"Skipped file not owned by current user: {path}")
        if file_stat.st_mtime > cutoff:
            return None
        resolved = path.resolve(strict=True)
        if not self._is_within(resolved, root):
            raise CleanupError(f"Skipped path outside cleanup root: {path}")
        return {
            "path": str(resolved),
            "relative_path": str(resolved.relative_to(root)),
            "bytes": file_stat.st_size,
            "modified_at_epoch": file_stat.st_mtime,
            "mtime_ns": file_stat.st_mtime_ns,
            "inode": file_stat.st_ino,
            "device": file_stat.st_dev,
            "links": file_stat.st_nlink,
            "suffix": path.suffix.lower(),
        }

    def _verify_candidate(self, root: Path, candidate: dict[str, Any]):
        path = Path(str(candidate.get("path", "")))
        self._ensure_path_components(root, path.parent)
        resolved = path.resolve(strict=True)
        if not self._is_within(resolved, root):
            raise CleanupError(f"Candidate path escaped cleanup root: {path}")
        file_stat = self._safe_lstat(path)
        self._match_snapshot(file_stat, candidate)
        if file_stat.st_nlink != 1:
            raise CleanupError(f"Candidate link count changed: {path}")
        return candidate, file_stat

    def _match_snapshot(self, file_stat, snapshot: dict[str, Any]) -> None:
        expected = (
            int(snapshot.get("device", -1)),
            int(snapshot.get("inode", -1)),
            int(snapshot.get("bytes", -1)),
            int(snapshot.get("mtime_ns", -1)),
        )
        current = (
            int(file_stat.st_dev),
            int(file_stat.st_ino),
            int(file_stat.st_size),
            int(file_stat.st_mtime_ns),
        )
        if current != expected:
            raise CleanupError("File metadata changed after dry-run; a new plan is required")

    def _validate_requested_root(self, value: str) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise CleanupError("Cleanup path must be a non-empty string")
        if any(marker in value for marker in config.COMMAND_SHELL_META_CHARS):
            raise CleanupError("Cleanup path contains blocked characters")
        requested = Path(value).expanduser().resolve(strict=True)
        allowed = next((root for root in self.allowed_roots if self._is_within(requested, root)), None)
        if allowed is None:
            allowed_text = ", ".join(str(root) for root in self.allowed_roots)
            raise CleanupError(f"Cleanup path is outside allowed roots: {allowed_text}")
        self._ensure_path_components(allowed, requested)
        if not requested.is_dir():
            raise CleanupError("Cleanup path is not a directory")
        return requested

    def _allowed_root_for(self, requested: Path) -> Path:
        allowed = next((root for root in self.allowed_roots if self._is_within(requested, root)), None)
        if allowed is None:
            raise CleanupError("Cleanup path is outside allowed roots")
        return allowed.resolve(strict=True)

    def _validate_destination(self, root: Path, destination: Path) -> None:
        resolved_parent = destination.parent.resolve(strict=True)
        if not self._is_within(resolved_parent, root):
            raise CleanupError("Restore target escaped cleanup root")
        self._ensure_path_components(root, resolved_parent)

    def _safe_directories(
        self,
        root: Path,
        current: Path,
        names: list[str],
        warnings: list[str],
    ) -> list[str]:
        safe = []
        for name in names:
            if name == QUARANTINE_DIR_NAME:
                continue
            child = current / name
            try:
                if child.is_symlink():
                    self._warning(warnings, f"Skipped symlink directory: {child}")
                    continue
                resolved = child.resolve(strict=True)
                if not self._is_within(resolved, root):
                    self._warning(warnings, f"Skipped directory outside root: {child}")
                    continue
            except OSError as exc:
                self._warning(warnings, f"Skipped directory {child}: {exc}")
                continue
            safe.append(name)
        return safe

    def _ensure_path_components(self, root: Path, target: Path) -> None:
        resolved_root = root.resolve(strict=True)
        resolved_target = target.resolve(strict=True)
        if not self._is_within(resolved_target, resolved_root):
            raise CleanupError("Path escaped the configured cleanup root")
        current = resolved_root
        for part in resolved_target.relative_to(resolved_root).parts:
            current = current / part
            if stat.S_ISLNK(os.lstat(current).st_mode):
                raise CleanupError(f"Symlink path component is not allowed: {current}")

    def _ensure_directory_not_symlink(self, path: Path) -> None:
        file_stat = os.lstat(path)
        if not stat.S_ISDIR(file_stat.st_mode) or stat.S_ISLNK(file_stat.st_mode):
            raise CleanupError("Controlled quarantine path is not a regular directory")

    def _ensure_controlled_directory(self, path: Path) -> None:
        self._ensure_directory_not_symlink(path)
        file_stat = os.lstat(path)
        if hasattr(os, "geteuid") and file_stat.st_uid != os.geteuid():
            raise CleanupError("Controlled quarantine directory has an unexpected owner")
        if os.name == "posix" and file_stat.st_mode & 0o022:
            raise CleanupError("Controlled quarantine directory is writable by other users")
        try:
            path.chmod(0o700)
        except OSError:
            pass

    def _safe_lstat(self, path: Path):
        try:
            file_stat = os.lstat(path)
        except OSError as exc:
            raise CleanupError(f"Unable to inspect file: {path}") from exc
        if stat.S_ISLNK(file_stat.st_mode):
            raise CleanupError(f"Symbolic links are not allowed: {path}")
        if not stat.S_ISREG(file_stat.st_mode):
            raise CleanupError(f"Only regular files can be quarantined: {path}")
        return file_stat

    def _load_manifest(self, quarantine_id: str) -> tuple[Path, dict[str, Any]]:
        for root in self.allowed_roots:
            candidate = root / QUARANTINE_DIR_NAME / quarantine_id
            manifest_path = candidate / "manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            self._ensure_controlled_directory(candidate.parent)
            self._ensure_controlled_directory(candidate)
            try:
                payload = self._read_manifest(manifest_path)
            except (OSError, json.JSONDecodeError) as exc:
                raise CleanupError("Unable to read quarantine manifest") from exc
            if not isinstance(payload, dict):
                raise CleanupError("Quarantine manifest format is invalid")
            return candidate.resolve(strict=True), payload
        raise CleanupError("Quarantine record not found")

    def _write_manifest(self, quarantine_root: Path, manifest: dict[str, Any]) -> None:
        self._ensure_controlled_directory(quarantine_root)
        temporary = quarantine_root / "manifest.tmp"
        target = quarantine_root / "manifest.json"
        payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        try:
            target.chmod(0o600)
        except OSError:
            pass

    def _read_manifest(self, path: Path) -> dict[str, Any]:
        before = os.lstat(path)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_nlink != 1
        ):
            raise CleanupError("Quarantine manifest is not a regular single-link file")
        if hasattr(os, "geteuid") and before.st_uid != os.geteuid():
            raise CleanupError("Quarantine manifest has an unexpected owner")
        if os.name == "posix" and before.st_mode & 0o022:
            raise CleanupError("Quarantine manifest is writable by other users")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            after = os.fstat(descriptor)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise CleanupError("Quarantine manifest changed while being opened")
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = -1
                payload = json.load(handle)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return payload

    def _rollback_quarantine(self, moved: list[dict[str, Any]]) -> list[str]:
        errors = []
        for item in reversed(moved):
            source = Path(item["quarantine_path"])
            destination = Path(item["original_path"])
            try:
                if source.exists() and not destination.exists():
                    os.replace(source, destination)
            except OSError as exc:
                errors.append(f"{destination}: {exc}")
        return errors

    def _rollback_restore(self, restored: list[dict[str, Any]]) -> list[str]:
        errors = []
        for item in reversed(restored):
            source = Path(item["original_path"])
            destination = Path(item["quarantine_path"])
            try:
                if source.exists() and not destination.exists():
                    os.replace(source, destination)
            except OSError as exc:
                errors.append(f"{source}: {exc}")
        return errors

    def _cleanup_expired_plans(self, *, exclude_plan_id: str = "") -> None:
        now = self.now_fn()
        expired = [
            plan_id
            for plan_id, plan in self._plans.items()
            if plan_id != exclude_plan_id and plan.get("expires_at", 0) < now
        ]
        for plan_id in expired:
            self._plans.pop(plan_id, None)

    def _quarantine_name(self, index: int, original_name: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", original_name)[:80] or "file"
        return f"{index:04d}_{uuid.uuid4().hex[:12]}_{safe_name}"

    def _digest(self, value: Any) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _constant_equal(self, left: str, right: str) -> bool:
        return bool(left and right) and hmac.compare_digest(left, right)

    def _bounded_int(self, value: Any, minimum: int, maximum: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise CleanupError(f"{name} must be an integer")
        if value < minimum or value > maximum:
            raise CleanupError(f"{name} must be between {minimum} and {maximum}")
        return value

    def _is_within(self, candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            return False

    def _is_forbidden_cleanup_root(self, root: Path) -> bool:
        if root.anchor and root == Path(root.anchor):
            return True
        return root.as_posix().rstrip("/") in FORBIDDEN_CLEANUP_ROOTS

    def _warning(self, warnings: list[str], message: str) -> None:
        if len(warnings) < 20:
            warnings.append(message)

    @property
    def executor_user(self) -> str:
        try:
            return getpass.getuser()
        except Exception:
            return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


_service = CleanupService()


def get_cleanup_service() -> CleanupService:
    return _service
