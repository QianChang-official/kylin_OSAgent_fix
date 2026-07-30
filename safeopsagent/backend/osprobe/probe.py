"""OS capability probe - detect what commands are available on target system."""
import platform
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SystemCapabilities:
    kernel: str = ""
    os_release: str = ""
    python_version: str = ""
    has_ss: bool = False
    has_netstat: bool = False
    has_journalctl: bool = False
    has_lsof: bool = False
    has_systemctl: bool = False
    cmd_paths: dict = field(default_factory=dict)
    unavailable: list = field(default_factory=list)


def run_probe() -> SystemCapabilities:
    cap = SystemCapabilities()
    cap.kernel = platform.release() or "unknown"
    cap.os_release = _read_os_release() or "unknown"
    cap.python_version = sys.version.split()[0] or "unknown"
    cap.has_ss = shutil.which("ss") is not None
    cap.has_netstat = shutil.which("netstat") is not None
    cap.has_journalctl = shutil.which("journalctl") is not None
    cap.has_lsof = shutil.which("lsof") is not None
    cap.has_systemctl = shutil.which("systemctl") is not None
    for cmd in [
        "ps", "df", "ss", "netstat", "journalctl", "lsof", "find", "du",
        "systemctl", "free", "whoami", "id", "last",
    ]:
        path = shutil.which(cmd)
        if path:
            cap.cmd_paths[cmd] = path
        else:
            cap.unavailable.append(cmd)
    return cap


def _read_os_release() -> Optional[str]:
    release_file = Path("/etc/os-release")
    try:
        if release_file.exists():
            return release_file.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    return None

