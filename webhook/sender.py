"""Asynchronous webhook delivery with retries, queueing, and cooldown controls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import threading
import time
from typing import Any

import httpx


@dataclass(slots=True)
class WebhookJob:
    payload: dict[str, Any]
    person_id: int
    not_before_monotonic: float


class WebhookSender:
    """Background webhook sender powered by an internal asyncio event loop."""

    def __init__(self, settings: Any, logger: Any) -> None:
        self.settings = settings
        self.logger = logger

        self._queue: asyncio.Queue[WebhookJob | None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client: httpx.AsyncClient | None = None
        self._running = False

        self._cooldown_lock = threading.Lock()
        self._last_person_event: dict[int, float] = {}
        self._next_global_slot = 0.0

        self._status_lock = threading.Lock()
        self._last_success: str | None = None
        self._last_failure: str | None = None
        self._last_error: str | None = None
        self._failed_log_path = Path("webhook_failed_events.jsonl")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

        deadline = time.time() + 5
        while (self._loop is None or self._queue is None) and time.time() < deadline:
            time.sleep(0.05)

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue()
        self._client = httpx.AsyncClient(timeout=self.settings.WEBHOOK_TIMEOUT)

        worker = self._loop.create_task(self._worker())
        try:
            self._loop.run_until_complete(worker)
        finally:
            self._loop.run_until_complete(self._shutdown_client())
            self._loop.close()

    async def _shutdown_client(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_signature(self, body: bytes) -> str:
        secret = self.settings.WEBHOOK_SECRET
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    async def _send_once(self, payload: dict[str, Any]) -> tuple[bool, str]:
        assert self._client is not None

        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.settings.WEBHOOK_SECRET:
            headers["X-Signature"] = self._build_signature(body)

        response = await self._client.post(self.settings.WEBHOOK_URL, content=body, headers=headers)
        if 200 <= response.status_code < 300:
            return True, f"HTTP {response.status_code}"
        return False, f"HTTP {response.status_code}: {response.text[:200]}"

    async def _send_with_retries(self, job: WebhookJob) -> bool:
        retries = max(0, int(self.settings.WEBHOOK_RETRY_COUNT))
        base_delay = max(1, int(self.settings.WEBHOOK_RETRY_DELAY))

        for attempt in range(retries + 1):
            try:
                ok, message = await self._send_once(job.payload)
                if ok:
                    with self._status_lock:
                        self._last_success = message
                        self._last_error = None
                    self.logger.info(
                        "Webhook delivered",
                        extra={"extra": {"person_id": job.person_id, "message": message, "attempt": attempt + 1}},
                    )
                    return True

                self.logger.warning(
                    "Webhook failed",
                    extra={"extra": {"person_id": job.person_id, "message": message, "attempt": attempt + 1}},
                )
                with self._status_lock:
                    self._last_failure = message
                    self._last_error = message
            except Exception as exc:  # pragma: no cover - network edge cases
                message = str(exc)
                self.logger.error(
                    "Webhook exception",
                    extra={"extra": {"person_id": job.person_id, "error": message, "attempt": attempt + 1}},
                )
                with self._status_lock:
                    self._last_failure = message
                    self._last_error = message

            if attempt < retries:
                await asyncio.sleep(base_delay * (2**attempt))

        self._persist_failed(job)
        return False

    def _persist_failed(self, job: WebhookJob) -> None:
        payload = {
            "failed_at": time.time(),
            "person_id": job.person_id,
            "payload": job.payload,
        }
        try:
            with self._failed_log_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            self.logger.error("Failed to persist failed webhook payload")

    async def _worker(self) -> None:
        assert self._queue is not None
        while True:
            job = await self._queue.get()
            if job is None:
                self._queue.task_done()
                break

            now = time.monotonic()
            if job.not_before_monotonic > now:
                await asyncio.sleep(job.not_before_monotonic - now)

            await self._send_with_retries(job)
            await asyncio.sleep(1.0)  # spacing for bursts of simultaneous entrants
            self._queue.task_done()

    def submit(self, payload: dict[str, Any], person_id: int) -> bool:
        """Queue a webhook respecting per-person and global cooldowns."""
        if not self._running or self._loop is None or self._queue is None:
            return False

        now = time.monotonic()
        with self._cooldown_lock:
            last_person = self._last_person_event.get(person_id, 0.0)
            if person_id >= 0 and now - last_person < float(self.settings.WEBHOOK_COOLDOWN_PERSON):
                self.logger.info(
                    "Webhook skipped due to person cooldown",
                    extra={"extra": {"person_id": person_id}},
                )
                return False

            not_before = max(now, self._next_global_slot)
            self._next_global_slot = not_before + float(self.settings.WEBHOOK_COOLDOWN_GLOBAL)
            self._last_person_event[person_id] = now

        job = WebhookJob(payload=payload, person_id=person_id, not_before_monotonic=not_before)
        fut = asyncio.run_coroutine_threadsafe(self._queue.put(job), self._loop)
        fut.result(timeout=2)
        return True

    def stop(self, flush_timeout: float = 15.0) -> None:
        if not self._running:
            return
        self._running = False

        if self._loop is not None and self._queue is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._queue.join(), self._loop).result(timeout=flush_timeout)
            except Exception:
                self.logger.warning("Webhook queue flush timed out")
            try:
                asyncio.run_coroutine_threadsafe(self._queue.put(None), self._loop).result(timeout=2)
            except Exception:
                self.logger.warning("Failed to send webhook shutdown sentinel")

        if self._thread is not None:
            self._thread.join(timeout=5)

    def status(self) -> dict[str, Any]:
        queue_size = 0
        if self._queue is not None:
            queue_size = self._queue.qsize()
        with self._status_lock:
            return {
                "last_success": self._last_success,
                "last_failure": self._last_failure,
                "last_error": self._last_error,
                "queue_size": queue_size,
                "running": self._running,
            }
