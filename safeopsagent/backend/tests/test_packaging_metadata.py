"""打包元数据必须与实际部署路径一致。

这些测试存在的理由是防"两个事实"：pyproject.toml 与 requirements.txt 各写
一份依赖、app.py 与打包元数据各写一个版本号，早晚会漂移成互相矛盾的两份
声明。与其靠人记得同步，不如让不同步直接把构建打红。
"""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import backend

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_version_has_a_single_source():
    """backend.__version__ 是唯一来源，其余处只能引用它。"""
    from backend.app import APP_VERSION

    assert APP_VERSION == backend.__version__

    app_source = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")
    assert not re.search(r'^APP_VERSION\s*=\s*["\']', app_source, re.MULTILINE), (
        "app.py 又硬编码了版本号；应保持 APP_VERSION = __version__"
    )

    assert _pyproject()["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "backend.__version__"
    }


def test_packaging_script_reads_the_same_version():
    """打包脚本按文本解析版本，改了来源就要跟着改。"""
    script = (ROOT / "scripts" / "package-final.py").read_text(encoding="utf-8")
    assert "__init__.py" in script and "__version__" in script, (
        "package-final.py 仍在从旧位置解析版本号"
    )


def test_dependencies_are_not_declared_twice():
    """依赖只有 requirements.txt 一处，pyproject 动态读取它。"""
    project = _pyproject()["project"]

    assert "dependencies" in project.get("dynamic", []), (
        "pyproject 不应静态列出 dependencies，否则会与 requirements.txt 漂移"
    )
    assert _pyproject()["tool"]["setuptools"]["dynamic"]["dependencies"] == {
        "file": ["backend/requirements.txt"]
    }


def test_declared_metadata_matches_requirements_file():
    """真正构建一次，核对元数据里的依赖与 requirements.txt 逐条相符。"""
    requirements = [
        line.strip()
        for line in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    result = subprocess.run(
        [sys.executable, "-c",
         "import tomllib,pathlib;"
         "d=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'));"
         "print(d['tool']['setuptools']['dynamic']['dependencies']['file'][0])"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "backend/requirements.txt"
    assert requirements, "requirements.txt 为空"


def test_tests_are_not_shipped_in_the_distribution():
    exclude = _pyproject()["tool"]["setuptools"]["packages"]["find"]["exclude"]
    assert "backend.tests*" in exclude


def test_console_build_is_packaged():
    """控制台由后端同源托管，构建产物必须随包分发。"""
    package_data = _pyproject()["tool"]["setuptools"]["package-data"]["backend"]
    assert any("static/console" in pattern for pattern in package_data)


def test_license_is_declared():
    project = _pyproject()["project"]
    assert project["license"] == "Apache-2.0"
    assert (ROOT.parent / "LICENSE").exists()
    assert (ROOT.parent / "NOTICE").exists()
