from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

NETWORK_PROBE_URL = "https://qt.gtimg.cn/q=sh600941"


@dataclass(frozen=True)
class CodexResult:
    exit_code: int
    version: str
    stdout_path: Path
    stderr_path: Path
    manifest_path: Path
    timed_out: bool = False
    paused: bool = False
    thread_id: str | None = None
    failure: str = ""


class CodexExecutor:
    def __init__(
        self,
        binary: str = "codex",
        timeout_seconds: int = 1_200,
        model: str | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_thread_started: Callable[[str], None] | None = None,
    ) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.should_stop = should_stop
        self.on_thread_started = on_thread_started

    def version(self) -> str:
        completed = subprocess.run(
            [self.binary, "--version"],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
        return (completed.stdout or completed.stderr).strip()

    def run(
        self,
        cwd: Path,
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
        resume_session_id: str | None = None,
    ) -> CodexResult:
        stdout_path = cwd / "codex.stdout.jsonl"
        stderr_path = cwd / "codex.stderr.log"
        try:
            check_network()
        except RuntimeError as exc:
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(str(exc), encoding="utf-8")
            return CodexResult(
                exit_code=-2,
                version=self.version(),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                manifest_path=manifest_path,
                failure=str(exc),
            )
        command = [
            self.binary,
            "exec",
        ]
        if resume_session_id:
            command.extend(["resume", resume_session_id])
        command.extend([
            "--json",
            "--skip-git-repo-check",
        ])
        if resume_session_id is None:
            command.extend(["--sandbox", "workspace-write"])
        command.extend(
            [
                "--config",
                "sandbox_workspace_write.network_access=true",
                "--output-schema",
                str(output_schema),
                "--output-last-message",
                str(manifest_path),
            ]
        )
        if resume_session_id is None:
            command.extend(["-C", str(cwd)])
        if self.model:
            command.extend(["--model", self.model])
        command.append(prompt)
        timed_out = False
        paused = False
        thread_id: str | None = None
        thread_notified = False
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_file:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    start_new_session=True,
                )
                deadline = time.monotonic() + self.timeout_seconds
                while True:
                    thread_id, thread_notified = self._capture_thread(
                        stdout_path,
                        thread_id,
                        thread_notified,
                    )
                    remaining = deadline - time.monotonic()
                    try:
                        exit_code = process.wait(timeout=min(0.5, max(remaining, 0.01)))
                        break
                    except subprocess.TimeoutExpired:
                        pass
                    if self._stop_requested():
                        paused = True
                        exit_code = -3
                        _terminate_process_group(process)
                        stderr_file.write("\nCodex execution paused by user.\n")
                        stderr_file.flush()
                        break
                    if remaining <= 0:
                        timed_out = True
                        process.kill()
                        process.wait()
                        exit_code = -1
                        stderr_file.write("\nCodex execution timed out.")
                        stderr_file.flush()
                        break
                thread_id, thread_notified = self._capture_thread(
                    stdout_path,
                    thread_id,
                    thread_notified,
                )
        except OSError as exc:
            exit_code = -1
            stderr_path.write_text(f"Codex 启动失败：{exc}", encoding="utf-8")
        return CodexResult(
            exit_code=exit_code,
            version=self.version(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=manifest_path,
            timed_out=timed_out,
            paused=paused,
            thread_id=thread_id or _read_thread_id(stdout_path),
        )

    def _stop_requested(self) -> bool:
        if self.should_stop is None:
            return False
        try:
            return self.should_stop()
        except Exception:
            return False

    def _capture_thread(
        self,
        stdout_path: Path,
        thread_id: str | None,
        notified: bool,
    ) -> tuple[str | None, bool]:
        if thread_id is None:
            thread_id = _read_thread_id(stdout_path)
        if thread_id and not notified:
            if self.on_thread_started is not None:
                with contextlib.suppress(Exception):
                    self.on_thread_started(thread_id)
            notified = True
        return thread_id, notified


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (OSError, ProcessLookupError):
        process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _read_thread_id(stdout_path: Path) -> str | None:
    if not stdout_path.is_file():
        return None
    with stdout_path.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
                if isinstance(thread_id, str) and thread_id:
                    return thread_id
    return None


def check_network() -> None:
    try:
        response = httpx.get(
            NETWORK_PROBE_URL,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "ValuationRadar/0.1"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Codex 网络预检失败：{exc}") from exc
    if not response.content:
        raise RuntimeError("Codex 网络预检失败：行情源返回空响应")
