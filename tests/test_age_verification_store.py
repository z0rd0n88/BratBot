"""Tests for AgeVerificationStore."""

from __future__ import annotations


class TestAgeVerificationStore:
    async def test_is_verified_returns_false_when_not_set(self, redis_mock) -> None:
        from bratbot.services.age_verification_store import AgeVerificationStore

        store = AgeVerificationStore(redis_mock)
        assert await store.is_verified(123456) is False

    async def test_is_verified_returns_true_after_set_verified(self, redis_mock) -> None:
        from bratbot.services.age_verification_store import AgeVerificationStore

        store = AgeVerificationStore(redis_mock)
        await store.set_verified(123456)
        assert await store.is_verified(123456) is True

    async def test_is_verified_returns_bool_not_int(self, redis_mock) -> None:
        from bratbot.services.age_verification_store import AgeVerificationStore

        store = AgeVerificationStore(redis_mock)
        result = await store.is_verified(123456)
        assert type(result) is bool

    async def test_different_users_are_independent(self, redis_mock) -> None:
        from bratbot.services.age_verification_store import AgeVerificationStore

        store = AgeVerificationStore(redis_mock)
        await store.set_verified(111)
        assert await store.is_verified(111) is True
        assert await store.is_verified(222) is False
