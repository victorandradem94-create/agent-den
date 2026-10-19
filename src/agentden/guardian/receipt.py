"""Rotation receipts: proof that a rotation completed, without any secret."""
import uuid
from datetime import timedelta

from .store import parse_utc

MARGIN_SECONDS = 3600  # rotate one hour before expiry


def new_receipt(agent, expires_in, now):
    if isinstance(expires_in, bool) or not isinstance(expires_in, int) or expires_in <= MARGIN_SECONDS:
        raise ValueError("token lifetime missing or too short")
    return {
        "agent": agent,
        "status": "rotation_completed",
        "rotation_id": str(uuid.uuid4()),
        "rotated_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
        "next_rotation_at": (now + timedelta(seconds=expires_in - MARGIN_SECONDS)).isoformat(),
    }


def check_receipt(receipt, agent, now):
    """Return None if the receipt is internally consistent, else a reason string."""
    try:
        if receipt.get("agent") != agent:
            return "receipt agent mismatch"
        if receipt.get("status") != "rotation_completed":
            return "receipt incomplete"
        uuid.UUID(str(receipt.get("rotation_id")))
        rotated = parse_utc(receipt.get("rotated_at"))
        nxt = parse_utc(receipt.get("next_rotation_at"))
        expires = parse_utc(receipt.get("expires_at"))
    except (ValueError, TypeError, AttributeError):
        return "receipt malformed"
    if not rotated <= now:
        return "receipt from the future"
    if not rotated < nxt < expires:
        return "receipt dates inconsistent"
    return None
