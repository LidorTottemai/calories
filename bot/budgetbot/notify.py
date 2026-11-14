"""Telegram delivery. Dry-run prints instead of sending, so the whole pipeline
can be exercised without a bot token ever existing."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import TELEGRAM_BASE, Settings

log = logging.getLogger(__name__)


class TelegramError(RuntimeError):
    pass


def _scrub(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def _call(settings: Settings, method: str, params: dict, timeout: int | None = None) -> dict:
    if not settings.telegram_token:
        raise TelegramError("TELEGRAM_BOT_TOKEN is not set")
    url = f"{TELEGRAM_BASE}/bot{settings.telegram_token}/{method}"
    body = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(url, data=body)

    last: Exception | None = None
    for attempt in range(1, settings.retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout or settings.http_timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if not payload.get("ok"):
                raise TelegramError(f"{method} refused: {payload.get('description')}")
            return payload.get("result", {})
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("description", "")
            except Exception:
                pass
            if 400 <= exc.code < 500:
                raise TelegramError(
                    _scrub(f"{method} returned {exc.code}: {detail or exc.reason}",
                           settings.telegram_token)
                ) from None
            last = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt < settings.retries:
            time.sleep(2 ** attempt)
    raise TelegramError(_scrub(f"{method} failed: {last}", settings.telegram_token))


class Notifier:
    """Sends to every configured chat; in dry-run, prints to stdout instead."""

    def __init__(self, settings: Settings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run

    def send(self, text: str) -> None:
        if self.dry_run:
            print("\n" + "─" * 46)
            print(f"[dry-run → {', '.join(self.settings.chat_ids) or 'no chat configured'}]")
            print(text)
            return
        for chat_id in self.settings.chat_ids:
            try:
                _call(self.settings, "sendMessage", {
                    "chat_id": chat_id,
                    "text": text,
                    "disable_web_page_preview": "true",
                })
            except TelegramError as exc:
                # One bad chat id must not stop the others.
                log.error("could not message %s: %s", chat_id, exc)

    # --------------------------------------------------------------- updates

    def poll_commands(self, offset: int) -> tuple[list[dict], int]:
        """Fetch pending /commands. Returns (messages, next offset)."""
        if self.dry_run:
            return [], offset
        params = {"timeout": "0", "allowed_updates": json.dumps(["message"])}
        if offset:
            params["offset"] = str(offset)
        updates = _call(self.settings, "getUpdates", params, timeout=20)
        messages, highest = [], offset
        for update in updates if isinstance(updates, list) else []:
            highest = max(highest, int(update.get("update_id", 0)) + 1)
            message = update.get("message") or {}
            if message.get("text"):
                messages.append(message)
        return messages, highest

    def reply(self, chat_id: str | int, text: str) -> None:
        if self.dry_run:
            print(f"\n[dry-run reply → {chat_id}]\n{text}")
            return
        _call(self.settings, "sendMessage", {
            "chat_id": str(chat_id),
            "text": text,
            "disable_web_page_preview": "true",
        })


def describe_chats(settings: Settings) -> list[dict]:
    """Everyone who has written to the bot, for the whoami helper."""
    updates = _call(settings, "getUpdates", {"timeout": "0"}, timeout=20)
    seen, out = set(), []
    for update in updates if isinstance(updates, list) else []:
        chat = (update.get("message") or {}).get("chat") or {}
        cid = chat.get("id")
        if cid is None or cid in seen:
            continue
        seen.add(cid)
        out.append({
            "id": cid,
            "type": chat.get("type", "?"),
            "title": chat.get("title") or " ".join(
                filter(None, [chat.get("first_name"), chat.get("last_name")])
            ) or chat.get("username", ""),
        })
    return out
