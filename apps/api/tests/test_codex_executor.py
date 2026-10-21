from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.integrations.codex import CodexExecutor


def test_codex_executor_runs_non_interactively(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="codex-cli 0.162.1", stderr="")

    class FakeProcess:
        def wait(self, timeout: int) -> int:
            assert timeout == 30
            return 0

        def kill(self) -> None:
            raise AssertionError("进程不应被终止")

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        calls.append((command, kwargs))
        stdout = kwargs["stdout"]
        stderr = kwargs["stderr"]
        assert hasattr(stdout, "write") and hasattr(stderr, "write")
        stdout.write('{"type":"done"}\n')
        stderr.write("")
        return FakeProcess()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    executor = CodexExecutor(binary="codex", timeout_seconds=30, model="test-model")

    result = executor.run(
        cwd=tmp_path,
        prompt="只返回 manifest",
        output_schema=tmp_path / "schema.json",
        manifest_path=tmp_path / "manifest.json",
    )

    command, options = calls[0]
    assert command[:3] == ["codex", "exec", "--ephemeral"]
    assert command[-1] == "只返回 manifest"
    assert "--approve-for-me" not in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is not None
    assert options["stderr"] is not None
    assert result.exit_code == 0
    assert result.version == "codex-cli 0.162.1"
    assert result.stdout_path.read_text(encoding="utf-8") == '{"type":"done"}\n'
