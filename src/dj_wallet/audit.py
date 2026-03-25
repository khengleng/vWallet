import json
from hashlib import sha256

from django.conf import settings
from django.utils import timezone

from .models import TransactionSignature


class AuditService:
    """
    Creates an audit hash for transactions and attaches to meta.
    """

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
    def attach_audit_hash(cls, txn):
        payload = cls._payload(txn)
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        audit_hash = sha256(data).hexdigest()
        meta = txn.meta or {}
        meta["audit_hash"] = audit_hash
        meta["audited_at"] = timezone.now().isoformat()
        txn.meta = meta
        txn.save(update_fields=["meta", "updated_at"])
        return audit_hash

    @classmethod
    def sign_audit(cls, txn, key_id="audit"):
        if not getattr(settings, "DJ_WALLET_SIGN_AUDIT", True):
            return None
        # Reuse TransactionSignature with HMAC scheme for audit hash
        from .signature import SignatureService

        sig = SignatureService.sign(txn, key_id=key_id)
        return sig
