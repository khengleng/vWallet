from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


class KeyProviderError(RuntimeError):
    pass


@dataclass
class KeyMaterial:
    """
    Container for key material. Keep this in-memory only.
    """

    value: str
    source: str = "unknown"


class KeyProvider:
    """
    Interface for key retrieval. Implement for HSM/KMS.
    """

    def get_app_signing_secret(self) -> KeyMaterial:
        raise NotImplementedError

    def get_chain_private_key(self) -> KeyMaterial:
        raise NotImplementedError


class EnvKeyProvider(KeyProvider):
    """
    Reads key material from environment-backed Django settings.
    """

    def get_app_signing_secret(self) -> KeyMaterial:
        secret = getattr(settings, "DJ_WALLET_SIGNING_SECRET", "")
        if not secret:
            raise KeyProviderError("DJ_WALLET_SIGNING_SECRET is not set")
        return KeyMaterial(value=secret, source="env")

    def get_chain_private_key(self) -> KeyMaterial:
        key = getattr(settings, "DJ_WALLET_CHAIN_PRIVATE_KEY", "")
        if not key:
            raise KeyProviderError("DJ_WALLET_CHAIN_PRIVATE_KEY is not set")
        return KeyMaterial(value=key, source="env")


def get_key_provider() -> KeyProvider:
    provider_path = getattr(
        settings, "DJ_WALLET_KEY_PROVIDER", "dj_wallet.security.keys.EnvKeyProvider"
    )
    provider_cls = import_string(provider_path)
    return provider_cls()


def get_app_signing_secret() -> str:
    return get_key_provider().get_app_signing_secret().value


def get_chain_private_key(allow_empty: bool = False) -> str:
    if allow_empty:
        try:
            return get_key_provider().get_chain_private_key().value
        except KeyProviderError:
            return ""
    return get_key_provider().get_chain_private_key().value
