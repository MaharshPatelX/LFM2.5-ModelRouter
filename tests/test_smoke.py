"""Small dependency-light checks for the repository foundation."""

from pathlib import Path

import pytest

from lfm_model_router import __version__
from lfm_model_router.cli import main
from lfm_model_router.config import load_project_config
from lfm_model_router.randomness import seed_python


def test_version_is_development_release() -> None:
    assert __version__ == "0.1.0.dev0"


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])

    assert capsys.readouterr().out.strip() == "lfm-model-router 0.1.0.dev0"


def test_base_config_loads() -> None:
    config = load_project_config(Path("configs/base.toml"))

    assert config.name == "LFM2.5-ModelRouter"
    assert config.seed == 3407
    assert config.data_dir == Path("data")


def test_negative_seed_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        seed_python(-1)
