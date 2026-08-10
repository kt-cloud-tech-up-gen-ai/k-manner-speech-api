"""Regression tests for the plan-acc breaker execution sandbox."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BREAKER_PATH = PROJECT_ROOT / ".agents" / "skills" / "plan-acc" / "breaker.py"

_SPEC = importlib.util.spec_from_file_location("plan_acc_breaker", BREAKER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
breaker = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = breaker
_SPEC.loader.exec_module(breaker)


def _git(repo: Path, *args: str, env: dict | None = None, check: bool = True):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def test_verify_git_writes_do_not_change_original_repository(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.name", "Breaker Test")
    _git(repo, "config", "user.email", "breaker@example.test")
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "--quiet", "-m", "initial")

    copy_root = tmp_path / "copy"
    breaker.make_copy(repo, copy_root)
    env = breaker.build_sample_env(tmp_path / "env")
    breaker.build_git_env(env, repo, copy_root)

    head = _git(copy_root, "rev-parse", "HEAD", env=env).stdout.strip()
    assert _git(copy_root, "remote", env=env).stdout.strip() == ""
    _git(copy_root, "update-ref", "refs/heads/verify-write", head, env=env)
    _git(copy_root, "config", "--local", "breaker.test-write", "isolated", env=env)

    assert _git(
        repo,
        "show-ref",
        "--verify",
        "--quiet",
        "refs/heads/verify-write",
        check=False,
    ).returncode != 0
    assert _git(
        repo,
        "config",
        "--local",
        "--get",
        "breaker.test-write",
        check=False,
    ).returncode != 0


def test_timeout_tracks_process_when_output_closes_early(tmp_path: Path):
    started = time.monotonic()

    _output, exit_code, timed_out, limit_hit = breaker.run_command(
        "exec 1>&- 2>&-; sleep 2",
        tmp_path,
        os.environ.copy(),
        timeout=0.1,
    )

    elapsed = time.monotonic() - started
    assert timed_out is True
    assert exit_code == -1
    assert limit_hit is False
    assert elapsed < 1.0
