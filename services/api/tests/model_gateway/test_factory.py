from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.model_gateway.factory import create_model_gateway
from app.model_gateway.fake_adapter import FakeModelGateway
from app.model_gateway.openai_adapter import OpenAICompatibleAdapter
from app.model_gateway.repository import ModelCallRepository


def settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {"database_path": tmp_path / "factory.db"}
    values.update(overrides)
    return Settings(**values)


def test_factory_defaults_to_fake_outside_production(tmp_path) -> None:
    repository = ModelCallRepository(tmp_path / "factory.db")
    gateway = create_model_gateway(settings(tmp_path), repository)
    assert isinstance(gateway, FakeModelGateway)


def test_factory_rejects_fake_in_production(tmp_path) -> None:
    repository = ModelCallRepository(tmp_path / "factory.db")
    with pytest.raises(ValueError, match="not allowed in production"):
        create_model_gateway(
            settings(tmp_path, environment="production", model_provider="fake"),
            repository,
        )


def test_factory_builds_configured_openai_compatible_adapter(tmp_path) -> None:
    repository = ModelCallRepository(tmp_path / "factory.db")
    gateway = create_model_gateway(
        settings(
            tmp_path,
            model_provider="openai",
            openai_api_key="test-key",
            openai_model="test-model",
            openai_base_url="http://provider.test/v1",
        ),
        repository,
    )
    assert isinstance(gateway, OpenAICompatibleAdapter)
    assert gateway.model_name == "test-model"
