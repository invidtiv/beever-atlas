"""Tests for AES-256-GCM credential encryption in beever_atlas.infra.crypto."""

from __future__ import annotations

import secrets

import pytest

# A valid 32-byte key expressed as a 64-character hex string.
_VALID_KEY_HEX = secrets.token_hex(32)


def _patch_key(monkeypatch, hex_key: str) -> None:
    """Set CREDENTIAL_MASTER_KEY and clear the lru_cache so the new value is picked up."""
    from beever_atlas.infra import config

    monkeypatch.setenv("CREDENTIAL_MASTER_KEY", hex_key)
    config.get_settings.cache_clear()


class TestEncryptDecryptRoundTrip:
    def test_round_trip_returns_original_dict(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        payload = {"token": "xoxb-abc", "team_id": "T123"}
        ciphertext, iv, tag = encrypt_credentials(payload)
        result = decrypt_credentials(ciphertext, iv, tag)

        assert result == payload

    def test_empty_dict_round_trip(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        ciphertext, iv, tag = encrypt_credentials({})
        result = decrypt_credentials(ciphertext, iv, tag)

        assert result == {}

    def test_large_payload_round_trip(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        payload = {f"key_{i}": "x" * 1000 for i in range(50)}
        ciphertext, iv, tag = encrypt_credentials(payload)
        result = decrypt_credentials(ciphertext, iv, tag)

        assert result == payload

    def test_unicode_and_emoji_values_survive_round_trip(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        payload = {"greeting": "こんにちは", "emoji": "🔐🦫", "mixed": "café résumé"}
        ciphertext, iv, tag = encrypt_credentials(payload)
        result = decrypt_credentials(ciphertext, iv, tag)

        assert result == payload


class TestRandomIV:
    def test_different_inputs_produce_different_ciphertexts(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from beever_atlas.infra.crypto import encrypt_credentials

        ct1, iv1, tag1 = encrypt_credentials({"a": "1"})
        ct2, iv2, tag2 = encrypt_credentials({"b": "2"})

        assert ct1 != ct2

    def test_same_input_produces_different_ciphertexts_due_to_random_iv(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from beever_atlas.infra.crypto import encrypt_credentials

        payload = {"token": "xoxb-same"}
        ct1, iv1, tag1 = encrypt_credentials(payload)
        ct2, iv2, tag2 = encrypt_credentials(payload)

        # Random IV means every encryption produces a distinct ciphertext.
        assert iv1 != iv2
        assert ct1 != ct2


class TestDecryptionFailures:
    def test_decrypt_with_wrong_iv_raises(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from cryptography.exceptions import InvalidTag

        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        payload = {"secret": "value"}
        ciphertext, iv, tag = encrypt_credentials(payload)
        wrong_iv = bytes([b ^ 0xFF for b in iv])

        with pytest.raises(InvalidTag):
            decrypt_credentials(ciphertext, wrong_iv, tag)

    def test_decrypt_with_tampered_ciphertext_raises(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from cryptography.exceptions import InvalidTag

        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        payload = {"secret": "value"}
        ciphertext, iv, tag = encrypt_credentials(payload)
        tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]

        with pytest.raises(InvalidTag):
            decrypt_credentials(tampered, iv, tag)

    def test_decrypt_with_tampered_tag_raises(self, monkeypatch):
        _patch_key(monkeypatch, _VALID_KEY_HEX)
        from cryptography.exceptions import InvalidTag

        from beever_atlas.infra.crypto import decrypt_credentials, encrypt_credentials

        payload = {"secret": "value"}
        ciphertext, iv, tag = encrypt_credentials(payload)
        tampered_tag = bytes([tag[0] ^ 0xFF]) + tag[1:]

        with pytest.raises(InvalidTag):
            decrypt_credentials(ciphertext, iv, tampered_tag)


class TestKeyValidation:
    def test_missing_key_raises_runtime_error(self, monkeypatch):
        from beever_atlas.infra import config

        monkeypatch.setenv("CREDENTIAL_MASTER_KEY", "")
        config.get_settings.cache_clear()
        from beever_atlas.infra.crypto import encrypt_credentials

        with pytest.raises(RuntimeError, match="CREDENTIAL_MASTER_KEY is not set"):
            encrypt_credentials({"x": "y"})

    def test_non_hex_key_raises_runtime_error(self, monkeypatch):
        from beever_atlas.infra import config

        monkeypatch.setenv("CREDENTIAL_MASTER_KEY", "not-valid-hex!" * 4)
        config.get_settings.cache_clear()
        from beever_atlas.infra.crypto import encrypt_credentials

        with pytest.raises(RuntimeError, match="64-character hex string"):
            encrypt_credentials({"x": "y"})

    def test_too_short_key_raises_runtime_error(self, monkeypatch):
        """A valid hex string that decodes to fewer than 32 bytes raises RuntimeError."""
        from beever_atlas.infra import config

        short_key = secrets.token_hex(16)  # 16 bytes = 32 hex chars, not 32 bytes
        monkeypatch.setenv("CREDENTIAL_MASTER_KEY", short_key)
        config.get_settings.cache_clear()
        from beever_atlas.infra.crypto import encrypt_credentials

        with pytest.raises(RuntimeError, match="32 bytes"):
            encrypt_credentials({"x": "y"})

    def test_too_long_key_raises_runtime_error(self, monkeypatch):
        """A valid hex string that decodes to more than 32 bytes raises RuntimeError."""
        from beever_atlas.infra import config

        long_key = secrets.token_hex(64)  # 64 bytes = 128 hex chars
        monkeypatch.setenv("CREDENTIAL_MASTER_KEY", long_key)
        config.get_settings.cache_clear()
        from beever_atlas.infra.crypto import encrypt_credentials

        with pytest.raises(RuntimeError, match="32 bytes"):
            encrypt_credentials({"x": "y"})
