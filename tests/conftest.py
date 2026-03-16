"""Shared test fixtures for BratBot tests."""

import pytest

from bratbot.services.llm_client import LLMClient


@pytest.fixture
def llm_client() -> LLMClient:
    """LLMClient with test defaults — no real server needed."""
    return LLMClient(
        base_url="http://test:8000",
        default_brat_level=3,
        timeout=10.0,
    )
