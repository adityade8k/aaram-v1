import gzip
import json
import time
import uuid
import base64
import asyncio
import logging
from typing import Literal
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from reachy_mini_conversation_app.memory import memory_path_for_instance


logger = logging.getLogger(__name__)
_WRITER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="experiment-log")
_CHUNK_BYTES = 192 * 1024


class ExperimentLog:
    """Append compact text events to one persistent gzip archive without blocking speech."""

    def __init__(self, instance_path: str | Path | None = None) -> None:
        """Use the app's persistent data directory, alongside long-term memory."""
        self.path = memory_path_for_instance(instance_path).with_name("experiment.jsonl.gz")
        self.session_id = uuid.uuid4().hex
        self._generation = uuid.uuid4().hex
        self._error: str | None = None

    def record(self, event: str, fields: dict[str, object]) -> None:
        """Queue an event with its capture time and session ID in arrival order."""
        entry = {"v": 1, "t": time.time_ns() // 1_000_000, "s": self.session_id, "e": event, **fields}
        try:
            encoded = (json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            self._error = "An event could not be encoded. See app logs."
            logger.error("Could not encode experiment event %s: %s", event, exc)
            return
        _WRITER.submit(self._append, encoded)

    def _append(self, encoded: bytes) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Complete gzip members keep each saved event readable across restarts.
            compressed = gzip.compress(encoded, compresslevel=9, mtime=0)
            with self.path.open("ab") as archive:
                start = archive.tell()
                try:
                    archive.write(compressed)
                    archive.flush()
                except OSError:
                    archive.truncate(start)
                    raise
        except OSError as exc:
            self._error = "Recording failed. Check available storage and folder permissions."
            logger.error("Could not append experiment log %s: %s", self.path, exc)

    async def access(
        self,
        action: Literal["status", "read", "clear"],
        *,
        offset: int = 0,
        limit: int = 0,
        generation: str = "",
    ) -> dict[str, object]:
        """Read or clear the archive in order after all already-queued writes."""
        return await asyncio.wrap_future(_WRITER.submit(self._access, action, offset, limit, generation))

    def _access(self, action: str, offset: int, limit: int, generation: str) -> dict[str, object]:
        if action == "clear":
            self.path.unlink(missing_ok=True)
            self._generation = uuid.uuid4().hex
            self._error = None
        size = self.path.stat().st_size if self.path.exists() else 0
        result: dict[str, object] = {
            "bytes": size,
            "filename": self.path.name,
            "path": str(self.path),
            "generation": self._generation,
            "error": self._error,
        }
        if action == "read":
            if generation != self._generation or not 0 <= offset <= limit <= size:
                raise ValueError("The log changed or the download range is invalid. Start the download again.")
            chunk = b""
            if offset < limit:
                with self.path.open("rb") as archive:
                    archive.seek(offset)
                    chunk = archive.read(min(_CHUNK_BYTES, limit - offset))
            result.update(content=base64.b64encode(chunk).decode("ascii"), next_offset=offset + len(chunk))
        return result
