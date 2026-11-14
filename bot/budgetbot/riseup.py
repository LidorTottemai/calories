"""Minimal RiseUp Exposed API client built on the standard library."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from .config import RISEUP_BASE, Settings

log = logging.getLogger(__name__)


class RiseUpError(RuntimeError):
    pass


def _scrub(text: str, secret: str) -> str:
    """Keep the token out of logs and exception messages."""
    return text.replace(secret, "riseup_pat_***") if secret else text


def fetch_month(settings: Settings, cashflow_month: str) -> list[dict]:
    """Return every transaction RiseUp files under the given YYYY-MM."""
    if not settings.riseup_pat:
        raise RiseUpError("RISEUP_PAT is not set")

    url = f"{RISEUP_BASE}/api/external/transactions?cashflowMonth={cashflow_month}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {settings.riseup_pat}",
            "Accept": "application/json",
        },
    )

    last: Exception | None = None
    for attempt in range(1, settings.retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=settings.http_timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            transactions = payload.get("transactions")
            if not isinstance(transactions, list):
                raise RiseUpError(f"unexpected payload shape for {cashflow_month}")
            log.debug("fetched %s: %d transactions", cashflow_month, len(transactions))
            return transactions
        except urllib.error.HTTPError as exc:
            # 4xx will not fix itself; stop immediately and say why.
            if 400 <= exc.code < 500:
                raise RiseUpError(
                    f"RiseUp returned {exc.code} for {cashflow_month}"
                    + (" - the token looks wrong or expired" if exc.code in (401, 403) else "")
                ) from None
            last = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt < settings.retries:
            time.sleep(2 ** attempt)

    raise RiseUpError(
        _scrub(f"could not reach RiseUp for {cashflow_month}: {last}", settings.riseup_pat)
    )
