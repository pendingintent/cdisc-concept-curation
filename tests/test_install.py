import platform
import sys

import pytest

import install


@pytest.mark.parametrize("version_info", [(3, 11, 0), (3, 11, 9), (3, 12, 0), (3, 12, 5)])
def test_check_python_version_accepts_supported_versions(monkeypatch, version_info):
    monkeypatch.setattr(sys, "version_info", version_info)
    install.check_python_version()  # must not raise/exit


@pytest.mark.parametrize("version_info", [(3, 9, 0), (3, 10, 0), (3, 13, 0), (3, 14, 6)])
def test_check_python_version_rejects_unsupported_versions(monkeypatch, version_info):
    """Issue #74: pandas==2.2.2 has no installable package for Python 3.13+ on
    some platforms, so the installer must refuse those versions with a clear
    message instead of letting pip fail deep inside a native build step."""
    monkeypatch.setattr(sys, "version_info", version_info)
    with pytest.raises(SystemExit):
        install.check_python_version()


def test_windows_start_launcher_does_not_invoke_powershell(tmp_path, monkeypatch):
    """A freshly-written Start.bat that shells out to `powershell -Command
    Start-Process` is exactly the kind of pattern AV heuristics quarantine
    right after install.py creates it, silently leaving the user with no
    launcher. Use plain cmd builtins (start/ping) instead."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(install, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(install, "ENV_FILE", tmp_path / ".env")

    path = install.create_start_launcher()

    assert path == tmp_path / "Start.bat"
    content = path.read_text()
    assert "powershell" not in content.lower()
    assert "http://localhost:8081" in content
    assert "python app.py" in content
