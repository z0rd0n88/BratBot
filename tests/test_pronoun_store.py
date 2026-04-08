"""Tests for PronounStore — stores user pronoun preference in Redis."""

from __future__ import annotations

import pytest

from bratbot.services.pronoun_store import PronounStore


@pytest.fixture
async def pronoun_store(redis_mock):
    return PronounStore(redis_mock)


class TestPronounStore:
    async def test_get_pronoun_default_is_male(self, pronoun_store: PronounStore) -> None:
        """Users with no preference default to 'male'."""
        result = await pronoun_store.get_pronoun(999999)
        assert result == "male"

    async def test_set_and_get_female(self, pronoun_store: PronounStore) -> None:
        """Setting 'female' round-trips correctly."""
        await pronoun_store.set_pronoun(123456, "female")
        assert await pronoun_store.get_pronoun(123456) == "female"

    async def test_set_and_get_other(self, pronoun_store: PronounStore) -> None:
        """Setting 'other' round-trips correctly."""
        await pronoun_store.set_pronoun(111111, "other")
        assert await pronoun_store.get_pronoun(111111) == "other"

    async def test_set_and_get_male(self, pronoun_store: PronounStore) -> None:
        """Setting 'male' explicitly round-trips correctly."""
        await pronoun_store.set_pronoun(222222, "male")
        assert await pronoun_store.get_pronoun(222222) == "male"

    async def test_set_overwrites_previous(self, pronoun_store: PronounStore) -> None:
        """Setting twice overwrites the first value."""
        await pronoun_store.set_pronoun(333333, "female")
        await pronoun_store.set_pronoun(333333, "other")
        assert await pronoun_store.get_pronoun(333333) == "other"

    async def test_set_invalid_value_raises(self, pronoun_store: PronounStore) -> None:
        """Invalid pronoun values raise ValueError."""
        with pytest.raises(ValueError, match="pronoun must be one of"):
            await pronoun_store.set_pronoun(444444, "nonbinary")

    async def test_different_users_are_independent(self, pronoun_store: PronounStore) -> None:
        """Two users have independent settings."""
        await pronoun_store.set_pronoun(555555, "female")
        await pronoun_store.set_pronoun(666666, "male")
        assert await pronoun_store.get_pronoun(555555) == "female"
        assert await pronoun_store.get_pronoun(666666) == "male"

    async def test_was_set_false_when_not_set(self, pronoun_store: PronounStore) -> None:
        """was_set() returns False before any preference is stored."""
        assert await pronoun_store.was_set(777777) is False

    async def test_was_set_true_after_set(self, pronoun_store: PronounStore) -> None:
        """was_set() returns True after a preference is stored."""
        await pronoun_store.set_pronoun(888888, "female")
        assert await pronoun_store.was_set(888888) is True
