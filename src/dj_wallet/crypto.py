import hashlib
import json
from decimal import Decimal


def _normalize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in value.items()}
    return value


def compute_transaction_hash(payload, algo="sha256"):
    """
    Compute a deterministic hash for a transaction payload.
    """
    normalized = _normalize_value(payload)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    h = hashlib.new(algo)
    h.update(encoded)
    return h.hexdigest()
