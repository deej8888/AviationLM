import pytest

from aerolm.settings import Settings


@pytest.fixture(autouse=True)
def ignore_local_model_activation(monkeypatch):
    """A developer's activated adapter must not turn unit tests into model inference."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
