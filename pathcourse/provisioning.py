"""
Standalone provisioning helpers — callable BEFORE you have an API key.

These functions exist outside PathCourseClient because you need them to get
your first API key. Once you have a key, construct a PathCourseClient and
use client.get_balance() / client.verify_key() to confirm everything is wired up.
"""

import os
import time
from typing import Optional

import httpx

from pathcourse.exceptions import PathCourseError, GatewayError, AuthenticationError


DEFAULT_BASE_URL = "https://gateway.pathcoursehealth.com"


def claim_key(
    tx_hash: str,
    wallet: str,
    base_url: Optional[str] = None,
    poll: bool = True,
    timeout: float = 60.0,
) -> dict:
    """
    Retrieve your PathCourse API key after depositing USDC on Base L2.

    Call this BEFORE constructing a PathCourseClient. No API key required —
    this endpoint is how you get one.

    Args:
        tx_hash:  The Base L2 transaction hash of your USDC deposit.
        wallet:   The wallet address the USDC was sent from (lowercased is fine).
        base_url: Override the gateway URL (default: https://gateway.pathcoursehealth.com).
        poll:     If True (default), retry on 202 Accepted until the key is ready,
                  up to ~3 minutes total. Set False to get the current state once.
        timeout:  Per-request timeout in seconds.

    Returns:
        dict with keys: api_key, agent_id, tier, balance_usdc, message, docs.

    Raises:
        PathCourseError: on 4xx/5xx from the gateway.
        GatewayError:    on network/timeout errors.

    Example:
        >>> import pathcourse
        >>> result = pathcourse.claim_key(
        ...     tx_hash="0xABC...",
        ...     wallet="0x123...",
        ... )
        >>> client = pathcourse.PathCourseClient(api_key=result["api_key"])
        >>> print(client.get_balance())
    """
    if not tx_hash or not wallet:
        raise PathCourseError("Both tx_hash and wallet are required.")

    url_base = (
        base_url
        or os.environ.get("PCH_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")

    max_attempts = 10 if poll else 1
    last_data: Optional[dict] = None

    for attempt in range(max_attempts):
        try:
            resp = httpx.get(
                f"{url_base}/v1/keys/claim",
                params={"tx_hash": tx_hash, "wallet": wallet},
                timeout=timeout,
            )
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")

        if resp.status_code == 200:
            return resp.json()

        try:
            data = resp.json() if resp.text else {}
        except Exception:
            data = {}
        last_data = data

        if resp.status_code == 202 and poll:
            time.sleep(data.get("retry_after_seconds", 15))
            continue
        if (
            resp.status_code == 404
            and data.get("error") == "payment_not_found"
            and poll
            and attempt < 3
        ):
            time.sleep(30)
            continue
        if resp.status_code >= 400:
            raise PathCourseError(
                data.get("message", f"Request failed with status {resp.status_code}"),
                status_code=resp.status_code,
                response=data,
            )
        if not poll:
            return data

    raise PathCourseError(
        "API key provisioning timed out. "
        "Verify the transaction has confirmed on Base and retry.",
        status_code=504,
        response=last_data,
    )


__all__ = ["claim_key"]
