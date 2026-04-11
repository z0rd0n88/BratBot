"""Tests for the IntensityStore service — stores user brat intensity in Redis."""

from __future__ import annotations

import pytest

from common.services.intensity_store import IntensityStore


@pytest.fixture
async def intensity_store(redis_mock):
    """Create an IntensityStore backed by mock Redis."""
    store = IntensityStore(redis_mock)
    return store


class TestIntensityStore:
    """Test Redis-backed intensity storage."""

    async def test_set_intensity_valid_level(self, intensity_store: IntensityStore) -> None:
        """Setting intensity with valid level (1-3) succeeds."""
        user_id = 123456
        await intensity_store.set_intensity(user_id, 2)

        stored = await intensity_store.get_intensity(user_id)
        assert stored == 2

    async def test_get_intensity_not_set(self, intensity_store: IntensityStore) -> None:
        """Getting intensity for user with no setting returns default (3)."""
        user_id = 999999
        result = await intensity_store.get_intensity(user_id)
        assert result == 3

    async def test_set_intensity_min_level(self, intensity_store: IntensityStore) -> None:
        """Level 1 (minimum) works."""
        user_id = 111111
        await intensity_store.set_intensity(user_id, 1)

        stored = await intensity_store.get_intensity(user_id)
        assert stored == 1

    async def test_set_intensity_max_level(self, intensity_store: IntensityStore) -> None:
        """Level 3 (maximum) works."""
        user_id = 222222
        await intensity_store.set_intensity(user_id, 3)

        stored = await intensity_store.get_intensity(user_id)
        assert stored == 3

    async def test_set_intensity_overwrites_previous(self, intensity_store: IntensityStore) -> None:
        """Setting intensity twice overwrites the first value."""
        user_id = 333333
        await intensity_store.set_intensity(user_id, 1)
        await intensity_store.set_intensity(user_id, 3)

        stored = await intensity_store.get_intensity(user_id)
        assert stored == 3

    async def test_set_intensity_invalid_level_too_low(
        self, intensity_store: IntensityStore
    ) -> None:
        """Setting level 0 raises ValueError."""
        user_id = 444444
        with pytest.raises(ValueError, match="intensity must be between 1 and 3"):
            await intensity_store.set_intensity(user_id, 0)

    async def test_set_intensity_invalid_level_too_high(
        self, intensity_store: IntensityStore
    ) -> None:
        """Setting level 4 raises ValueError."""
        user_id = 555555
        with pytest.raises(ValueError, match="intensity must be between 1 and 3"):
            await intensity_store.set_intensity(user_id, 4)

    async def test_different_users_independent(self, intensity_store: IntensityStore) -> None:
        """Different users have independent intensity settings."""
        await intensity_store.set_intensity(666666, 1)
        await intensity_store.set_intensity(777777, 3)

        assert await intensity_store.get_intensity(666666) == 1
        assert await intensity_store.get_intensity(777777) == 3

    async def test_was_set_returns_false_when_not_set(
        self, intensity_store: IntensityStore
    ) -> None:
        """was_set() returns False when user hasn't set intensity."""
        user_id = 888888
        result = await intensity_store.was_set(user_id)
        assert result is False

    async def test_was_set_returns_true_when_set(self, intensity_store: IntensityStore) -> None:
        """was_set() returns True when user has set intensity."""
        user_id = 999999
        await intensity_store.set_intensity(user_id, 2)
        result = await intensity_store.was_set(user_id)
        assert result is True
