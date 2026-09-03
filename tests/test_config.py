import importlib
from unittest.mock import patch


def test_config_calls_load_dotenv_on_import():
    """The installer writes a .env file for non-technical users; Config must
    call load_dotenv() so those values are actually read into os.environ.
    (python-dotenv is a dependency but nothing called load_dotenv() before
    this test was written, so a generated .env file was silently ignored.)
    """
    import config

    with patch("dotenv.load_dotenv") as mock_load_dotenv:
        importlib.reload(config)
        mock_load_dotenv.assert_called_once()

    importlib.reload(config)
