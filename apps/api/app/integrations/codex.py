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
            with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_file:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                )
                try:
                    exit_code = process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.kill()
                    process.wait()
                    exit_code = -1
                    stderr_file.write("\nCodex execution timed out.")
                    stderr_file.flush()
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
        )
