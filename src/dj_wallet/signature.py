import hmac
import json
from hashlib import sha256

from django.conf import settings

from .crypto import _normalize_value
from .models import TransactionSignature


class SignatureService:
    """
    Default app-level signer using HMAC-SHA256.
    """

    scheme = TransactionSignature.SCHEME_HMAC_SHA256

    @staticmethod
    def _get_secret():
        secret = getattr(settings, "DJ_WALLET_SIGNING_SECRET", "")
        if not secret:
            raise RuntimeError("DJ_WALLET_SIGNING_SECRET is not set")
        return secret.encode("utf-8")

    @staticmethod
    def _payload(txn):
        return {
            "uuid": str(txn.uuid),
            "wallet_id": txn.wallet_id,
            "type": txn.type,
            "amount": str(txn.amount),
            "status": txn.status,
            "created_at": txn.created_at.isoformat() if txn.created_at else "",
            "tx_hash": txn.tx_hash,
        }

    @classmethod
    def sign(cls, txn, key_id=""):
        payload = _normalize_value(cls._payload(txn))
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        signature = hmac.new(cls._get_secret(), data, sha256).hexdigest()
        return TransactionSignature.objects.create(
            transaction=txn,
            scheme=cls.scheme,
            signature=signature,
            key_id=key_id,
        )

    @classmethod
    def verify(cls, txn, signature):
        payload = _normalize_value(cls._payload(txn))
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        expected = hmac.new(cls._get_secret(), data, sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
