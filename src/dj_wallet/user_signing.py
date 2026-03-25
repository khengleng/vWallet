import json
import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import HolderKey, SignatureNonce, TransactionSignature


class MissingDependency(RuntimeError):
    pass


def _require_eth_account():
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except Exception as exc:  # pragma: no cover
        raise MissingDependency(
            "eth-account is required for secp256k1 verification."
        ) from exc
    return Account, encode_defunct


class UserSigningService:
    """
    Handles user-side signatures for permissioned actions.
    """

    @staticmethod
    def issue_nonce(holder, ttl_seconds=300):
        ct = ContentType.objects.get_for_model(holder)
        nonce = secrets.token_hex(16)
        expires_at = timezone.now() + timedelta(seconds=ttl_seconds)
        SignatureNonce.objects.create(
            holder_type=ct, holder_id=holder.pk, nonce=nonce, expires_at=expires_at
        )
        return nonce

    @staticmethod
    def _payload(holder, action, amount, nonce):
        return {
            "holder_id": holder.pk,
            "holder_type": holder._meta.label_lower,
            "action": action,
            "amount": str(Decimal(str(amount))),
            "nonce": nonce,
        }

    @classmethod
    def verify(cls, holder, action, amount, nonce, signature, key_id):
        ct = ContentType.objects.get_for_model(holder)
        key = HolderKey.objects.filter(
            holder_type=ct, holder_id=holder.pk, key_id=key_id, is_active=True
        ).first()
        if not key:
            return False, "unknown_key"

        nonce_obj = SignatureNonce.objects.filter(
            nonce=nonce, holder_type=ct, holder_id=holder.pk
        ).first()
        if not nonce_obj or nonce_obj.used_at is not None:
            return False, "nonce_invalid"
        if nonce_obj.expires_at < timezone.now():
            return False, "nonce_expired"

        payload = cls._payload(holder, action, amount, nonce)
        message = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        if key.scheme == HolderKey.SCHEME_SECP256K1:
            Account, encode_defunct = _require_eth_account()
            message_hash = encode_defunct(text=message)
            recovered = Account.recover_message(message_hash, signature=signature)
            if recovered.lower() != key.public_key.lower():
                return False, "signature_mismatch"
        else:
            return False, "scheme_not_supported"

        nonce_obj.used_at = timezone.now()
        nonce_obj.save(update_fields=["used_at"])
        return True, ""

    @staticmethod
    def attach_signature(txn, signature, key_id, signer):
        key = HolderKey.objects.filter(key_id=key_id).first()
        return TransactionSignature.objects.create(
            transaction=txn,
            scheme=TransactionSignature.SCHEME_SECP256K1,
            public_key=key.public_key if key else "",
            signature=signature,
            key_id=key_id,
            signer=signer,
        )
