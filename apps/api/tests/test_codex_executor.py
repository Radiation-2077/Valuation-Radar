from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.integrations.codex as codex_module
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
        def wait(self, timeout: float) -> int:
            assert 0 < timeout <= 1
            return 0

        def kill(self) -> None:
            raise AssertionError("进程不应被终止")

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        calls.append((command, kwargs))
        stdout = kwargs["stdout"]
        stderr = kwargs["stderr"]
        assert hasattr(stdout, "write") and hasattr(stderr, "write")
        stdout.write(
            '{"type":"thread.started","thread_id":"01a16ee4-91fb-7a81-97a7-a18bbcdbc38c"}\n'
        )
        stdout.write('{"type":"done"}\n')
        stderr.write("")
        stdout.flush()
        return FakeProcess()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_module, "check_network", lambda: None)
    started_threads: list[str] = []
    executor = CodexExecutor(
        binary="codex",
        timeout_seconds=30,
        model="test-model",
        on_thread_started=started_threads.append,
    )

    result = executor.run(
        cwd=tmp_path,
        prompt="只返回 manifest",
        output_schema=tmp_path / "schema.json",
        manifest_path=tmp_path / "manifest.json",
    )

    command, options = calls[0]
    assert command[:3] == ["codex", "exec", "--json"]
    assert "--ephemeral" not in command
    assert command[-1] == "只返回 manifest"
    assert "--approve-for-me" not in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert (
        command[command.index("--config") + 1]
        == "sandbox_workspace_write.network_access=true"
    )
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is not None
    assert options["stderr"] is not None
    assert options["start_new_session"] is True
    assert options["cwd"] == tmp_path
    assert result.exit_code == 0
    assert result.version == "codex-cli 0.162.1"
    assert result.thread_id == "01a16ee4-91fb-7a81-97a7-a18bbcdbc38c"
    assert started_threads == ["01a16ee4-91fb-7a81-97a7-a18bbcdbc38c"]
    assert result.stdout_path.read_text(encoding="utf-8").endswith('{"type":"done"}\n')


def test_codex_executor_stops_before_model_when_network_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        codex_module,
        "check_network",
        lambda: (_ for _ in ()).throw(RuntimeError("Codex 网络预检失败：blocked")),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="codex-cli 0.162.1",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("网络失败时不应启动模型")
        ),
    )

    result = CodexExecutor().run(
        cwd=tmp_path,
        prompt="不应执行",
        output_schema=tmp_path / "schema.json",
        manifest_path=tmp_path / "manifest.json",
    )

    assert result.exit_code == -2
    assert "网络预检失败" in result.failure
    assert "网络预检失败" in result.stderr_path.read_text(encoding="utf-8")


def test_codex_executor_stops_when_pause_is_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    killed_groups: list[int] = []

    class PausableProcess:
        pid = 4321

        def wait(self, timeout: float) -> int:
            if timeout > 1:
                return -15
            raise subprocess.TimeoutExpired("codex", timeout)

    def fake_popen(command: list[str], **kwargs: object) -> PausableProcess:
        del command, kwargs
        return PausableProcess()

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="codex-cli 0.162.1",
            stderr="",
        ),
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_module, "check_network", lambda: None)
    monkeypatch.setattr(codex_module.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        codex_module.os,
        "killpg",
        lambda pid, signal_number: killed_groups.append(pid),
    )

    result = CodexExecutor(
        timeout_seconds=30,
        should_stop=lambda: True,
    ).run(
        cwd=tmp_path,
        prompt="暂停任务",
        output_schema=tmp_path / "schema.json",
        manifest_path=tmp_path / "manifest.json",
    )

    assert result.paused is True
    assert result.exit_code == -3
    assert killed_groups == [4321]
    assert "paused by user" in result.stderr_path.read_text(encoding="utf-8")


def test_codex_executor_resumes_existing_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class FakeProcess:
        def wait(self, timeout: float) -> int:
            assert 0 < timeout <= 1
            return 0

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        calls.append((command, kwargs))
        stdout = kwargs["stdout"]
        stdout.write(
            '{"type":"thread.started","thread_id":"01a16ee4-91fb-7a81-97a7-a18bbcdbc38c"}\n'
        )
        stdout.flush()
        return FakeProcess()

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="codex-cli 0.162.1",
            stderr="",
        ),
    )
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_module, "check_network", lambda: None)

    result = CodexExecutor(timeout_seconds=30).run(
        cwd=tmp_path,
        prompt="从断点继续",
        output_schema=tmp_path / "schema.json",
        manifest_path=tmp_path / "manifest.json",
        resume_session_id="01a16ee4-91fb-7a81-97a7-a18bbcdbc38c",
    )

    command, options = calls[0]
    assert command[:4] == [
        "codex",
        "exec",
        "resume",
        "01a16ee4-91fb-7a81-97a7-a18bbcdbc38c",
    ]
    assert "--sandbox" not in command
    assert "-C" not in command
    assert options["cwd"] == tmp_path
    assert result.thread_id == "01a16ee4-91fb-7a81-97a7-a18bbcdbc38c"
