"""Tests for the VerbosityStore service — stores user verbosity level in Redis."""

from __future__ import annotations

import pytest

from bratbot.services.verbosity_store import VerbosityStore


@pytest.fixture
async def verbosity_store(redis_mock):
    return VerbosityStore(redis_mock)


class TestVerbosityStore:
    async def test_get_verbosity_not_set_returns_default(
        self, verbosity_store: VerbosityStore
    ) -> None:
        """Getting verbosity for user with no setting returns default (2)."""
        result = await verbosity_store.get_verbosity(999999)
        assert result == 2

    async def test_set_and_get_verbosity(self, verbosity_store: VerbosityStore) -> None:
        """Setting verbosity persists and can be retrieved."""
        await verbosity_store.set_verbosity(123456, 3)
        assert await verbosity_store.get_verbosity(123456) == 3

    async def test_set_verbosity_min_level(self, verbosity_store: VerbosityStore) -> None:
        """Level 1 (minimum) works."""
        await verbosity_store.set_verbosity(111111, 1)
        assert await verbosity_store.get_verbosity(111111) == 1

    async def test_set_verbosity_max_level(self, verbosity_store: VerbosityStore) -> None:
        """Level 3 (maximum) works."""
        await verbosity_store.set_verbosity(222222, 3)
        assert await verbosity_store.get_verbosity(222222) == 3

    async def test_set_verbosity_overwrites_previous(self, verbosity_store: VerbosityStore) -> None:
        """Setting verbosity twice overwrites the first value."""
        await verbosity_store.set_verbosity(333333, 1)
        await verbosity_store.set_verbosity(333333, 3)
        assert await verbosity_store.get_verbosity(333333) == 3

    async def test_set_verbosity_invalid_too_low(self, verbosity_store: VerbosityStore) -> None:
        """Setting level 0 raises ValueError."""
        with pytest.raises(ValueError, match="verbosity must be between 1 and 3"):
            await verbosity_store.set_verbosity(444444, 0)

    async def test_set_verbosity_invalid_too_high(self, verbosity_store: VerbosityStore) -> None:
        """Setting level 4 raises ValueError."""
        with pytest.raises(ValueError, match="verbosity must be between 1 and 3"):
            await verbosity_store.set_verbosity(555555, 4)

    async def test_different_users_independent(self, verbosity_store: VerbosityStore) -> None:
        """Different users have independent verbosity settings."""
        await verbosity_store.set_verbosity(666666, 1)
        await verbosity_store.set_verbosity(777777, 3)
        assert await verbosity_store.get_verbosity(666666) == 1
        assert await verbosity_store.get_verbosity(777777) == 3

    async def test_was_set_returns_false_when_not_set(
        self, verbosity_store: VerbosityStore
    ) -> None:
        """was_set() returns False when user hasn't set verbosity."""
        assert await verbosity_store.was_set(888888) is False

    async def test_was_set_returns_true_when_set(self, verbosity_store: VerbosityStore) -> None:
        """was_set() returns True after setting verbosity."""
        await verbosity_store.set_verbosity(999999, 2)
        assert await verbosity_store.was_set(999999) is True
