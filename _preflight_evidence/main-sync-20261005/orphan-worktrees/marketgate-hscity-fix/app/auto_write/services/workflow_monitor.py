from __future__ import annotations

import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import gettempdir
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowMonitor:
    """Small runtime event store. Events come from actual wrapped service calls."""

    def __init__(self, state_path: str | Path | None = None, max_runs: int = 50):
        self.state_path = Path(state_path or Path(gettempdir()) / "auto_write_operator" / "workflow_runs.json")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_runs = max_runs
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.state_path.exists():
            return []
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, runs: list[dict[str, Any]]) -> None:
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(runs[-self.max_runs:], ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def start_run(self, kind: str, label: str, metadata: dict[str, Any] | None = None) -> str:
        with self._lock:
            runs = self._load()
            run_id = uuid.uuid4().hex[:10]
            runs.append(
                {
                    "run_id": run_id,
                    "kind": kind,
                    "label": label,
                    "status": "RUNNING",
                    "started_at": _now(),
                    "ended_at": "",
                    "metadata": metadata or {},
                    "steps": [],
                    "error": "",
                }
            )
            self._save(runs)
            return run_id

    def _mutate(self, run_id: str, fn) -> None:
        with self._lock:
            runs = self._load()
            for run in runs:
                if run.get("run_id") == run_id:
                    fn(run)
                    break
            self._save(runs)

    def start_step(self, run_id: str, key: str, label: str, service: str, details: dict | None = None) -> None:
        def mutate(run):
            run["steps"].append(
                {
                    "key": key,
                    "label": label,
                    "service": service,
                    "status": "RUNNING",
                    "started_at": _now(),
                    "ended_at": "",
                    "details": details or {},
                    "error": "",
                }
            )
        self._mutate(run_id, mutate)

    def finish_step(self, run_id: str, key: str, details: dict | None = None) -> None:
        def mutate(run):
            for step in reversed(run["steps"]):
                if step.get("key") == key and step.get("status") == "RUNNING":
                    step["status"] = "SUCCESS"
                    step["ended_at"] = _now()
                    if details:
                        step["details"].update(details)
                    return
        self._mutate(run_id, mutate)

    def fail_step(self, run_id: str, key: str, error: str) -> None:
        def mutate(run):
            for step in reversed(run["steps"]):
                if step.get("key") == key and step.get("status") == "RUNNING":
                    step["status"] = "FAILED"
                    step["ended_at"] = _now()
                    step["error"] = error[:1200]
                    return
        self._mutate(run_id, mutate)

    def finish_run(self, run_id: str, metadata: dict | None = None) -> None:
        def mutate(run):
            run["status"] = "SUCCESS"
            run["ended_at"] = _now()
            if metadata:
                run["metadata"].update(metadata)
        self._mutate(run_id, mutate)

    def fail_run(self, run_id: str, error: str) -> None:
        def mutate(run):
            run["status"] = "FAILED"
            run["ended_at"] = _now()
            run["error"] = error[:1200]
        self._mutate(run_id, mutate)

    @contextmanager
    def step(self, run_id: str, key: str, label: str, service: str, details: dict | None = None):
        self.start_step(run_id, key, label, service, details)
        try:
            yield
        except Exception as exc:
            self.fail_step(run_id, key, f"{type(exc).__name__}: {exc}")
            raise
        else:
            self.finish_step(run_id, key)

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._load()))[: max(1, min(limit, self.max_runs))]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            for run in self._load():
                if run.get("run_id") == run_id:
                    return run
        return None
