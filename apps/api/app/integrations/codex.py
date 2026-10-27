from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
        debug: bool = False,
        trace: bool = False,
        should_stop: Callable[[], bool] | None = None,
        on_thread_started: Callable[[str], None] | None = None,
    ) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.model = model
        self.debug = debug
        self.trace = trace
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
        launch_command, debug_path, trace_path = self._prepare_launch(
            cwd=cwd,
            command=command,
            prompt=prompt,
            output_schema=output_schema,
            manifest_path=manifest_path,
        )
        timed_out = False
        paused = False
        thread_id: str | None = None
        thread_notified = False
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_file:
                process = subprocess.Popen(
                    launch_command,
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    start_new_session=True,
                )
                if self.debug and debug_path is not None:
                    _append_debug(debug_path, f"pid={process.pid}")
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
            if self.debug and debug_path is not None:
                _append_debug(debug_path, f"launch_error={exc!r}")
        if self.debug and debug_path is not None:
            _append_debug(
                debug_path,
                f"exit_code={exit_code}",
                f"manifest_exists={manifest_path.is_file()}",
                f"stdout_bytes={stdout_path.stat().st_size if stdout_path.exists() else 0}",
                f"stderr_bytes={stderr_path.stat().st_size if stderr_path.exists() else 0}",
            )
            if trace_path is not None:
                _append_enoent_trace(debug_path, trace_path)
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

    def _prepare_launch(
        self,
        *,
        cwd: Path,
        command: list[str],
        prompt: str,
        output_schema: Path,
        manifest_path: Path,
    ) -> tuple[list[str], Path | None, Path | None]:
        if not self.debug:
            return command, None, None

        debug_path = cwd / "codex.debug.log"
        launch_command = command
        trace_path: Path | None = None
        trace_header = "trace=disabled"
        if self.trace:
            strace_binary = shutil.which("strace")
            if strace_binary is None:
                trace_header = "trace=requested_but_strace_missing"
            else:
                trace_path = cwd / "codex.trace.log"
                launch_command = [
                    strace_binary,
                    "-f",
                    "-tt",
                    "-T",
                    "-s",
                    "256",
                    "-e",
                    "trace=%file,%process",
                    "-o",
                    str(trace_path),
                    *command,
                ]
                trace_header = f"trace={trace_path}"

        resolved_binary = shutil.which(self.binary)
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        debug_lines = [
            "",
            f"=== Codex launch {datetime.now(UTC).isoformat()} ===",
            f"binary={self.binary}",
            f"resolved_binary={resolved_binary or '<not found>'}",
            f"cwd={cwd}",
            f"cwd_exists={cwd.is_dir()}",
            f"schema={output_schema}",
            f"schema_exists={output_schema.is_file()}",
            f"manifest_path={manifest_path}",
            f"manifest_parent_exists={manifest_path.parent.is_dir()}",
            f"prompt_chars={len(prompt)}",
            f"prompt_sha256={prompt_digest}",
            f"PATH={os.environ.get('PATH', '')}",
            f"HOME={os.environ.get('HOME', '')}",
            f"CODEX_HOME={os.environ.get('CODEX_HOME', '<unset>')}",
            f"RUST_LOG={os.environ.get('RUST_LOG', '<unset>')}",
            trace_header,
            f"command={shlex.join(_redact_prompt(launch_command, prompt))}",
        ]
        _write_debug(debug_path, debug_lines)
        return launch_command, debug_path, trace_path

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


def _redact_prompt(command: list[str], prompt: str) -> list[str]:
    redacted = list(command)
    if redacted and redacted[-1] == prompt:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        redacted[-1] = f"<prompt:{len(prompt)}chars:sha256:{digest}>"
    return redacted


def _write_debug(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines).lstrip("\n") + "\n", encoding="utf-8")


def _append_debug(path: Path, *lines: str) -> None:
    with path.open("a", encoding="utf-8") as file:
        for line in lines:
            file.write(f"{line}\n")


def _append_enoent_trace(debug_path: Path, trace_path: Path) -> None:
    if not trace_path.is_file():
        _append_debug(debug_path, "trace_file=<missing>")
        return
    missing_lines = [
        line.rstrip()
        for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if "ENOENT" in line
    ]
    _append_debug(debug_path, f"trace_file={trace_path}")
    if missing_lines:
        _append_debug(debug_path, "trace_enoent=<last 40>", *missing_lines[-40:])
    else:
        _append_debug(debug_path, "trace_enoent=<none>")


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
