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
