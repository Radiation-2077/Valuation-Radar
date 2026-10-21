from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexResult:
    exit_code: int
    version: str
    stdout_path: Path
    stderr_path: Path
    manifest_path: Path
    timed_out: bool = False


class CodexExecutor:
    def __init__(
        self,
        binary: str = "codex",
        timeout_seconds: int = 1_200,
        model: str | None = None,
    ) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self.model = model

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
    ) -> CodexResult:
        stdout_path = cwd / "codex.stdout.jsonl"
        stderr_path = cwd / "codex.stderr.log"
        command = [
            self.binary,
            "exec",
            "--ephemeral",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(output_schema),
            "--output-last-message",
            str(manifest_path),
            "-C",
            str(cwd),
        ]
        if self.model:
            command.extend(["--model", self.model])
        command.append(prompt)
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=self.timeout_seconds,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = -1
            stdout = _as_text(exc.stdout)
            stderr = _as_text(exc.stderr) + "\nCodex execution timed out."
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        return CodexResult(
            exit_code=exit_code,
            version=self.version(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            manifest_path=manifest_path,
            timed_out=timed_out,
        )


def _as_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
