#!/usr/bin/env python3
"""breaker.py -- AC gate harness for plan-acc (v3 design).

usage: breaker.py <plan.md> --repo <project-root>
                  [--require-coverage] [--repeat N] [--accept-unguarded T7,T12] [--json]

What `GUARDED` means (and does not mean) -- this is the whole point of the tool:

    GUARDED = this Verify command reacts to this Breaker mutation. It does NOT mean
    the requirement itself is protected, that Verify exercises the real entry point,
    or that the failure is the *right* failure for the *right* reason.

This harness only rules out "the verification observes nothing" -- it never proves
"the verification observes the correct thing." See the boundary table (IDs A-P) in
plan-acc/SKILL.md for everything this gate deliberately does not check.

Standard library only. No third-party dependencies, nothing installed, nothing
downloaded.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

# --------------------------------------------------------------------------
# Constants (design doc SS3, SS4, SS12)
# --------------------------------------------------------------------------

GUARANTEE_LINES = [
    "GUARDED = 이 Verify 가 이 Breaker 에 반응함. 요구 속성의 보호를 뜻하지 않음.",
    "이 게이트는 \"검증이 아무것도 관측하지 않는다\"를 배제할 뿐, "
    "\"올바른 것을 관측한다\"를 증명하지 않는다.",
]

FIELD_NAMES = ("AC", "Verify", "Breaker", "Expect-red", "Observed", "Negative")
UNOBSERVED_MARKER = "미관찰"

TEST_GLOBS = ("test_*.py", "*_test.py", "*_test.go", "*.test.*", "*.spec.*")
TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}

# NOTE ON DEVIATION FROM THE LITERAL SPEC ("re.escape(s) != s"):
# CPython's re.escape (3.7+) also escapes space, hyphen and other characters that
# are common and harmless in literal signatures. Using it verbatim rejects the
# design's own canonical example ("AC-T1-STORED-VALUE" contains hyphens) and any
# multi-word literal with a space. We check against an explicit regex-metachar set
# instead -- it still blocks the `FAIL_?` bypass E-1 exists for (the `?` is in this
# set), while accepting hyphenated/spaced identifiers.
REGEX_METACHARS = set(".^$*+?{}[]\\|()")

GENERIC_FAILURE_VOCAB = {
    "fail", "failed", "failure", "error", "errors", "exception", "assert",
    "assertion", "assertionerror", "panic", "fatal", "build", "tests", "test",
    "result", "some", "all", "not", "ok", "exit", "code", "status", "traceback",
    "err",
}

FORBIDDEN_HINT_PATTERNS = [
    r"ImportError", r"ModuleNotFoundError", r"SyntaxError", r"cannot find package",
    r"Cannot find module", r"ERR_MODULE_NOT_FOUND", r"undefined:", r"no such column",
    r"no such table", r"error: expected", r"collection error", r"ERROR collecting",
    r"build failed", r"Compilation failed", r"cannot find symbol",
]

NA_REASONS = {"external-service", "human-visual", "hardware-perf", "manual-approval"}

EXCLUDE_COPY_DIRS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "target", ".next", "dist",
    "build", ".gradle", ".pnpm-store", ".uv-cache", ".uv-python",
    "__pycache__", ".pytest_cache", ".mypy_cache",
}
# Windows commonly disallows os.symlink without Developer Mode/admin rights.
# Python virtualenvs are reproducible and Verify commands can recreate them,
# so only package-manager dependency trees are linked into isolation copies.
DEP_LINK_DIRS = {"node_modules", "vendor", ".pnpm-store"}

ENV_CACHE_SUBDIRS = ("home", "tmp", "cache", "gocache", "gomodcache", "npmcache")
SECRET_ENV_PREFIXES = ("AWS_", "GOOGLE_", "GCP_")
SECRET_ENV_SUFFIXES = ("_TOKEN", "_SECRET", "_KEY", "_PASSWORD")

OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024
DEFAULT_TIMEOUT = 600
DEFAULT_REPEAT = 2
TERM_GRACE_SECONDS = 3

ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
FENCE_RE = re.compile(r"^\s*```")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*\S)\s*$")
HEADING_ID_RE = re.compile(r"^([A-Za-z][\w-]*)\s*[:.]")
LOOSE_FIELD_RE = re.compile(r"^\s*-?\s*\**\s*([A-Za-z][A-Za-z-]*)\s*\**\s*:", re.IGNORECASE)


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class FieldError:
    line: int
    message: str


@dataclass
class ReplaceBreaker:
    path: str
    old: str
    new: str
    line: int


@dataclass
class DeleteBreaker:
    path: str
    line: int


@dataclass
class RenameBreaker:
    src: str
    dst: str
    line: int


@dataclass
class NABreaker:
    reason: str
    line: int


@dataclass
class BreakerParseError:
    line: int
    message: str


BreakerEntry = Union[ReplaceBreaker, DeleteBreaker, RenameBreaker, NABreaker, BreakerParseError]


@dataclass
class ACBlock:
    ac_id: str
    start_line: int
    end_line: int
    verify: Optional[str]
    verify_line: Optional[int]
    expect_red: Optional[str]
    expect_red_line: Optional[int]
    observed_raw: Optional[str]
    observed_line: Optional[int]
    negative: Optional[str]
    breakers: list
    scenario_count: int
    parse_errors: list
    raw_text: str


@dataclass
class CaseResult:
    verdict: str
    detail: str
    breaker_index: int
    snippet: str = ""


# --------------------------------------------------------------------------
# Parsing: fenced-code tracking
# --------------------------------------------------------------------------

def strip_fenced_code(lines: list) -> list:
    """Return a bool per line: True if the line is a fence marker or inside one.

    Fenced lines are excluded from all structural parsing so example AC blocks
    inside ``` fences are never mistaken for real ones.
    """
    in_code = False
    flags = []
    for line in lines:
        if FENCE_RE.match(line):
            flags.append(True)
            in_code = not in_code
        else:
            flags.append(in_code)
    return flags


def _field_patterns(name: str):
    esc = re.escape(name)
    return [
        re.compile(rf"^\s*-\s*\*\*{esc}:\*\*\s?(.*)$"),
        re.compile(rf"^\s*\*\*{esc}:\*\*\s?(.*)$"),
        re.compile(rf"^\s*-\s*{esc}:\s?(.*)$"),
    ]


FIELD_REGEXES = {name: _field_patterns(name) for name in FIELD_NAMES}
BASE_SHA_PATTERNS = _field_patterns("Base-SHA")


def match_field(line: str):
    """Return (name, value) if the line is one of the 3 accepted markup forms
    for a known field name; else None."""
    for name, patterns in FIELD_REGEXES.items():
        for pat in patterns:
            m = pat.match(line)
            if m:
                return name, m.group(1).strip()
    return None


def detect_deviant_field(line: str):
    """A line that looks like it's trying to declare a known field but doesn't
    match any of the 3 accepted forms. Returns the field name it *looks like*,
    or None."""
    m = LOOSE_FIELD_RE.match(line)
    if not m:
        return None
    token = m.group(1)
    for name in FIELD_NAMES:
        if token.lower() == name.lower():
            return name
    return None


def find_base_sha(text: str):
    """Search the whole document (outside fences) for **Base-SHA:** <hex>.

    Returns (found: bool, raw_value: Optional[str]).
    """
    lines = text.split("\n")
    code_flags = strip_fenced_code(lines)
    for i, line in enumerate(lines):
        if code_flags[i]:
            continue
        for pat in BASE_SHA_PATTERNS:
            m = pat.match(line)
            if m:
                return True, m.group(1).strip()
    return False, None


# --------------------------------------------------------------------------
# Parsing: breaker syntax (direct backtick scan -- not a regex split, since
# `::`/`->` can legitimately appear inside the quoted content)
# --------------------------------------------------------------------------

def extract_backtick_segments(s: str, count: int):
    """Scan left-to-right, extracting `count` backtick-delimited segments in
    order. Returns None if fewer than `count` are found (unterminated or
    missing)."""
    segments = []
    i, n = 0, len(s)
    while i < n and len(segments) < count:
        if s[i] == "`":
            j = s.find("`", i + 1)
            if j == -1:
                return None
            segments.append(s[i + 1:j])
            i = j + 1
        else:
            i += 1
    if len(segments) < count:
        return None
    return segments


def parse_breaker_value(value: str, line: int) -> BreakerEntry:
    v = value.strip()
    if v.startswith("N/A"):
        rest = v[3:].strip()
        rest = rest.lstrip("—-:").strip()
        if rest in NA_REASONS:
            return NABreaker(reason=rest, line=line)
        return BreakerParseError(
            line,
            f"N/A breaker reason must be one of {sorted(NA_REASONS)}, got: {rest!r}",
        )
    if v.startswith("DELETE"):
        segs = extract_backtick_segments(v, 1)
        if not segs:
            return BreakerParseError(line, "expected format: DELETE `<path>`")
        return DeleteBreaker(path=segs[0], line=line)
    if v.startswith("RENAME"):
        segs = extract_backtick_segments(v, 2)
        if not segs:
            return BreakerParseError(line, "expected format: RENAME `<src>` -> `<dst>`")
        return RenameBreaker(src=segs[0], dst=segs[1], line=line)
    segs = extract_backtick_segments(v, 3)
    if not segs:
        return BreakerParseError(
            line, "expected format: `<path>` :: `<old>` -> `<new>` (or DELETE/RENAME/N/A)"
        )
    return ReplaceBreaker(path=segs[0], old=segs[1], new=segs[2], line=line)


# --------------------------------------------------------------------------
# Parsing: AC blocks
# --------------------------------------------------------------------------

def build_ac_block(ac_id: str, start_line: int, end_line: int, raw_lines: list, idxs: list) -> ACBlock:
    fields = {name: [] for name in FIELD_NAMES}
    errors = []
    current_field = None
    scenario_count = 0
    raw_text_parts = []

    for idx in idxs:
        line = raw_lines[idx]
        lineno = idx + 1
        raw_text_parts.append(line)
        if "Given" in line and "When" in line and "Then" in line:
            scenario_count += 1
        f = match_field(line)
        if f:
            name, value = f
            fields[name].append({"value": value, "line": lineno, "extra": []})
            current_field = (name, len(fields[name]) - 1)
            continue
        deviant = detect_deviant_field(line)
        if deviant:
            errors.append(FieldError(
                lineno,
                f"'{deviant}:' 필드 표기가 3가지 허용 형식(- **{deviant}:** / **{deviant}:** / "
                f"- {deviant}:) 중 어느 것과도 일치하지 않음: {line.strip()!r}",
            ))
            continue
        if current_field is not None and line.strip():
            name, eidx = current_field
            fields[name][eidx]["extra"].append(line.strip())

    def single_value(name: str):
        entries = fields[name]
        if len(entries) != 1:
            report_line = entries[0]["line"] if entries else start_line
            lines_str = ", ".join(str(e["line"]) for e in entries) if entries else "0"
            errors.append(FieldError(
                report_line,
                f"필드 '{name}' 은 블록당 정확히 1개여야 함, {len(entries)}개 발견 (행: {lines_str})",
            ))
            return None, None
        e = entries[0]
        value = " ".join([e["value"]] + e["extra"]).strip() if e["extra"] else e["value"]
        return value, e["line"]

    verify, verify_line = single_value("Verify")
    expect_red, expect_red_line = single_value("Expect-red")
    observed, observed_line = single_value("Observed")

    negative_entries = fields["Negative"]
    if len(negative_entries) > 1:
        errors.append(FieldError(
            negative_entries[0]["line"],
            f"필드 'Negative' 는 최대 1개만 허용, {len(negative_entries)}개 발견",
        ))
        negative = None
    elif negative_entries:
        e = negative_entries[0]
        negative = " ".join([e["value"]] + e["extra"]).strip()
    else:
        negative = None

    breakers = [parse_breaker_value(e["value"], e["line"]) for e in fields["Breaker"]]
    if not breakers:
        errors.append(FieldError(start_line, "필드 'Breaker' 는 블록당 최소 1개 필요"))

    return ACBlock(
        ac_id=ac_id,
        start_line=start_line,
        end_line=end_line,
        verify=verify,
        verify_line=verify_line,
        expect_red=expect_red,
        expect_red_line=expect_red_line,
        observed_raw=observed,
        observed_line=observed_line,
        negative=negative,
        breakers=breakers,
        scenario_count=scenario_count,
        parse_errors=errors,
        raw_text="\n".join(raw_text_parts),
    )


def parse_plan(text: str) -> list:
    raw_lines = text.split("\n")
    n = len(raw_lines)
    code_flags = strip_fenced_code(raw_lines)
    blocks = []
    current_heading_id = None
    id_counts = {}
    seq_counter = 0

    i = 0
    while i < n:
        if code_flags[i]:
            i += 1
            continue
        line = raw_lines[i]
        heading_m = HEADING_RE.match(line)
        if heading_m:
            id_m = HEADING_ID_RE.match(heading_m.group(2))
            if id_m:
                current_heading_id = id_m.group(1)
            i += 1
            continue
        f = match_field(line)
        if f and f[0] == "AC":
            start = i
            seq_counter += 1
            base_id = current_heading_id or f"AC{seq_counter}"
            cnt = id_counts.get(base_id, 0)
            id_counts[base_id] = cnt + 1
            ac_id = base_id if cnt == 0 else f"{base_id}#{cnt + 1}"

            j = i + 1
            while j < n:
                if code_flags[j]:
                    j += 1
                    continue
                if HEADING_RE.match(raw_lines[j]):
                    break
                f2 = match_field(raw_lines[j])
                if f2 and f2[0] == "AC":
                    break
                j += 1

            block_idxs = [k for k in range(start, j) if not code_flags[k]]
            blocks.append(build_ac_block(ac_id, start + 1, j, raw_lines, block_idxs))
            i = j
            continue
        i += 1
    return blocks


# --------------------------------------------------------------------------
# Static checks -- S-1, S-2, S-3, E-1..E-6 (SS3.2/SS4.2). All read-only against
# --repo; none of these touch a copy.
# --------------------------------------------------------------------------

def is_test_path(relpath) -> bool:
    p = Path(relpath)
    name = p.name
    if any(fnmatch.fnmatch(name, pat) for pat in TEST_GLOBS):
        return True
    if any(part in TEST_DIR_NAMES for part in p.parts[:-1]):
        return True
    return False


def has_symlink_component(base: Path, relpath: str) -> bool:
    cur = base
    for part in Path(relpath).parts:
        cur = cur / part
        if cur.is_symlink():
            return True
    return False


def check_breaker_static(repo_root: Path, breaker) -> Optional[tuple]:
    """Returns (code, message) if invalid, else None. Only called for real
    (non-N/A, non-parse-error) breaker entries."""
    if isinstance(breaker, ReplaceBreaker):
        paths = [breaker.path]
    elif isinstance(breaker, DeleteBreaker):
        paths = [breaker.path]
    elif isinstance(breaker, RenameBreaker):
        paths = [breaker.src, breaker.dst]
    else:
        return None

    for p in paths:
        if is_test_path(p):
            return ("INVALID/self-referential", f"breaker path targets a test-path pattern: {p}")

    repo_resolved = repo_root.resolve()
    for p in paths:
        resolved = (repo_root / p).resolve()
        try:
            resolved.relative_to(repo_resolved)
        except ValueError:
            return ("INVALID/path-escape", f"breaker path escapes repo root: {p}")
        if has_symlink_component(repo_root, p):
            return ("INVALID/path-escape", f"breaker path has a symlink component: {p}")

    if isinstance(breaker, ReplaceBreaker):
        target = repo_root / breaker.path
        try:
            st = os.lstat(target)
        except OSError:
            return ("INVALID/ambiguous-old", f"breaker target file missing: {breaker.path}")
        if not stat.S_ISREG(st.st_mode):
            return ("INVALID/ambiguous-old", f"breaker target is not a regular file: {breaker.path}")
        try:
            content = target.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return ("INVALID/ambiguous-old", f"breaker target is not valid UTF-8 text: {breaker.path}")
        if breaker.old == breaker.new:
            return ("INVALID/ambiguous-old", "'old' and 'new' are identical")
        occurrences = content.count(breaker.old)
        if occurrences != 1:
            return (
                "INVALID/ambiguous-old",
                f"'old' occurs {occurrences} times in {breaker.path} (must be exactly 1)",
            )
    elif isinstance(breaker, DeleteBreaker):
        target = repo_root / breaker.path
        try:
            st = os.lstat(target)
        except OSError:
            return ("INVALID/ambiguous-old", f"DELETE target does not exist: {breaker.path}")
        if not stat.S_ISREG(st.st_mode):
            return ("INVALID/ambiguous-old", f"DELETE target is not a regular file: {breaker.path}")
    elif isinstance(breaker, RenameBreaker):
        src = repo_root / breaker.src
        dst = repo_root / breaker.dst
        try:
            st = os.lstat(src)
        except OSError:
            return ("INVALID/ambiguous-old", f"RENAME source does not exist: {breaker.src}")
        if not stat.S_ISREG(st.st_mode):
            return ("INVALID/ambiguous-old", f"RENAME source is not a regular file: {breaker.src}")
        if dst.exists() or dst.is_symlink():
            return ("INVALID/ambiguous-old", f"RENAME destination already exists: {breaker.dst}")
        if not dst.parent.is_dir():
            return ("INVALID/ambiguous-old", f"RENAME destination parent does not exist: {breaker.dst}")
    return None


def iter_test_files(repo_root: Path):
    for current, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_COPY_DIRS]
        rel_dir = Path(current).relative_to(repo_root)
        for fname in filenames:
            relpath = rel_dir / fname if str(rel_dir) != "." else Path(fname)
            if is_test_path(relpath):
                yield Path(current) / fname


def literal_in_any_test_file(repo_root: Path, literal: str) -> bool:
    for path in iter_test_files(repo_root):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if literal in content:
            return True
    return False


def check_expect_red(expect_red: Optional[str], verify_cmd: Optional[str], repo_root: Path) -> Optional[tuple]:
    """E-1..E-5 (block-level; E-6 is per-breaker, see check_e6)."""
    if expect_red is None:
        return None  # already reported as a field-count error
    if any(ch in REGEX_METACHARS for ch in expect_red):
        return ("INVALID/regex-meta", f"Expect-red contains regex metacharacters: {expect_red!r}")
    if len(expect_red) < 6:
        return ("INVALID/too-short", f"Expect-red is shorter than 6 characters: {expect_red!r}")
    tokens = re.findall(r"[A-Za-z0-9]+", expect_red)
    if tokens and all(t.lower() in GENERIC_FAILURE_VOCAB for t in tokens):
        return ("INVALID/generic", f"Expect-red is made up entirely of generic failure vocabulary: {expect_red!r}")
    if verify_cmd and expect_red in verify_cmd:
        return ("INVALID/in-command", "Expect-red literal appears inside the Verify command string")
    if not literal_in_any_test_file(repo_root, expect_red):
        return ("INVALID/not-in-test", "Expect-red literal not found in any test-path file under --repo")
    return None


def check_e6(expect_red: Optional[str], breaker) -> Optional[tuple]:
    if expect_red and isinstance(breaker, ReplaceBreaker) and expect_red in breaker.new:
        return ("INVALID/in-breaker", "Expect-red literal appears inside the Breaker's 'new' text")
    return None


FORBIDDEN_HINT_RE = [re.compile(p) for p in FORBIDDEN_HINT_PATTERNS]


def detect_forbidden_hint(text: str) -> Optional[str]:
    for pat in FORBIDDEN_HINT_RE:
        if pat.search(text):
            return pat.pattern
    return None


# --------------------------------------------------------------------------
# Output normalization (SS4.4)
# --------------------------------------------------------------------------

def normalize_output(text: str) -> str:
    text = ANSI_OSC_RE.sub("", text)
    text = ANSI_CSI_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))


# --------------------------------------------------------------------------
# Execution (SS4.4, SS4.5) -- argv Popen, no shell=True, process-group timeout,
# byte-capped drain, bytes-then-surrogateescape decode.
# --------------------------------------------------------------------------

def run_command(cmd: str, cwd: Path, env: dict, timeout: int = DEFAULT_TIMEOUT):
    """Returns (normalized_text, exit_code, timed_out, limit_hit)."""
    bash = "/bin/bash"
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        bash = str(git_bash)
    proc = subprocess.Popen(
        [bash, "-o", "pipefail", "-c", cmd],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    # start_new_session=True makes the child the leader of a new process group,
    # so its PID is the PGID even if the short-lived shell exits immediately.
    process_group = proc.pid
    deadline = time.monotonic() + timeout

    chunks = []
    state = {"total": 0, "limit_hit": False}

    def signal_process_group(sig) -> None:
        try:
            os.killpg(process_group, sig)
        except (ProcessLookupError, PermissionError):
            pass

    def reader():
        while True:
            try:
                chunk = proc.stdout.read(65536)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            chunks.append(chunk)
            state["total"] += len(chunk)
            if state["total"] > OUTPUT_LIMIT_BYTES and not state["limit_hit"]:
                state["limit_hit"] = True
                signal_process_group(signal.SIGKILL)
                break

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    timed_out = False
    try:
        proc.wait(timeout=max(0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True

    if not timed_out:
        t.join(max(0, deadline - time.monotonic()))
        timed_out = t.is_alive()

    if timed_out:
        signal_process_group(signal.SIGTERM)
        grace_deadline = time.monotonic() + TERM_GRACE_SECONDS
        if proc.poll() is None:
            try:
                proc.wait(timeout=max(0, grace_deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        t.join(max(0, grace_deadline - time.monotonic()))
        if proc.poll() is None or t.is_alive():
            signal_process_group(signal.SIGKILL)
        if proc.poll() is None:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Verify process survived SIGKILL") from exc
        t.join(10)

    raw = b"".join(chunks)
    text = raw.decode("utf-8", errors="surrogateescape")
    text = normalize_output(text)
    exit_code = -1 if timed_out else proc.returncode
    return text, exit_code, timed_out, state["limit_hit"]


# --------------------------------------------------------------------------
# Isolation: copy, dependency symlinks, git env, sandboxed env vars (SS4.5, SS4.6)
# --------------------------------------------------------------------------

def make_copy(repo_root: Path, dest_root: Path) -> None:
    def ignore(dir_path, names):
        ignored = set()
        for name in names:
            if name in EXCLUDE_COPY_DIRS:
                ignored.add(name)
                continue
            full = os.path.join(dir_path, name)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                ignored.add(name)
            elif stat.S_ISFIFO(st.st_mode) or stat.S_ISSOCK(st.st_mode):
                ignored.add(name)
        return ignored

    shutil.copytree(repo_root, dest_root, ignore=ignore, symlinks=False)
    link_dependency_dirs(repo_root, dest_root)


def link_dependency_dirs(repo_root: Path, dest_root: Path) -> None:
    for current, dirnames, _filenames in os.walk(repo_root, topdown=True):
        cur_path = Path(current)
        rel = cur_path.relative_to(repo_root)
        keep = []
        for d in dirnames:
            if d in EXCLUDE_COPY_DIRS:
                if d in DEP_LINK_DIRS:
                    src = cur_path / d
                    if src.is_dir() and not src.is_symlink():
                        dst = dest_root / rel / d if str(rel) != "." else dest_root / d
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        if not dst.exists() and not dst.is_symlink():
                            os.symlink(src.resolve(), dst)
                continue  # never descend into an excluded dir
            keep.append(d)
        dirnames[:] = keep


def check_pnpm_workspace_layout(repo_root: Path, dest_root: Path) -> bool:
    """Return False if a dependency symlink in the copy resolves outside the
    original repo's node_modules -- i.e. Verify would silently import
    un-mutated original source instead of the sandboxed copy."""
    node_modules = dest_root / "node_modules"
    if not node_modules.exists():
        return True
    original_node_modules = (repo_root / "node_modules").resolve()

    def check_dir(d: Path) -> bool:
        try:
            entries = list(d.iterdir())
        except OSError:
            return True
        for entry in entries:
            if not entry.is_symlink():
                continue
            try:
                real = entry.resolve()
            except OSError:
                continue
            inside = real == original_node_modules or original_node_modules in real.parents
            if not inside:
                return False
        return True

    if not check_dir(node_modules):
        return False
    for scope_dir in node_modules.glob("@*"):
        if scope_dir.is_dir() and not check_dir(scope_dir):
            return False
    return True


def build_sample_env(root: Path) -> dict:
    subdirs = {name: root / name for name in ENV_CACHE_SUBDIRS}
    for d in subdirs.values():
        d.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    for k in list(env.keys()):
        if k == "DATABASE_URL" or k.startswith(SECRET_ENV_PREFIXES) or k.endswith(SECRET_ENV_SUFFIXES):
            del env[k]

    env["HOME"] = str(subdirs["home"])
    env["TMPDIR"] = str(subdirs["tmp"])
    env["XDG_CACHE_HOME"] = str(subdirs["cache"])
    env["GOCACHE"] = str(subdirs["gocache"])
    env["GOMODCACHE"] = str(subdirs["gomodcache"])
    env["npm_config_cache"] = str(subdirs["npmcache"])
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    return env


def resolve_git_dir(repo_root: Path) -> Optional[Path]:
    dot_git = repo_root / ".git"
    if not dot_git.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            p = Path(result.stdout.strip())
            if p.exists():
                return p
    except (OSError, subprocess.SubprocessError):
        pass
    return dot_git if dot_git.is_dir() else None


def build_git_env(env: dict, repo_root: Path, copy_root: Path) -> None:
    """Point Verify at an isolated clone while preserving the original index."""
    git_dir = resolve_git_dir(repo_root)
    if git_dir is None:
        return

    isolated_repo = Path(env["TMPDIR"]).parent / "git-repo"
    clone_env = dict(env)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        clone_env.pop(name, None)
    try:
        result = subprocess.run(
            [
                "git", "clone", "--quiet", "--no-checkout", "--no-hardlinks",
                str(repo_root), str(isolated_repo),
            ],
            capture_output=True,
            text=True,
            env=clone_env,
            timeout=DEFAULT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"failed to isolate Git metadata: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git clone exited {result.returncode}"
        raise RuntimeError(f"failed to isolate Git metadata: {detail}")

    result = subprocess.run(
        ["git", "-C", str(isolated_repo), "remote", "remove", "origin"],
        capture_output=True,
        text=True,
        env=clone_env,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"git remote remove exited {result.returncode}"
        raise RuntimeError(f"failed to detach isolated Git metadata: {detail}")

    isolated_git_dir = isolated_repo / ".git"
    env["GIT_DIR"] = str(isolated_git_dir)
    env["GIT_WORK_TREE"] = str(copy_root.resolve())
    env["GIT_OPTIONAL_LOCKS"] = "0"
    index_src = git_dir / "index"
    index_dst = Path(env["TMPDIR"]) / "git-index"
    if index_src.exists():
        try:
            shutil.copy2(index_src, index_dst)
        except OSError:
            pass
    env["GIT_INDEX_FILE"] = str(index_dst)


def ensure_writable(p: Path) -> None:
    try:
        st = p.stat()
        os.chmod(p, st.st_mode | stat.S_IWUSR | stat.S_IWGRP)
    except FileNotFoundError:
        pass


def apply_breaker(copy_root: Path, breaker) -> None:
    if isinstance(breaker, ReplaceBreaker):
        target = copy_root / breaker.path
        ensure_writable(target)
        content = target.read_text(encoding="utf-8")
        new_content = content.replace(breaker.old, breaker.new, 1)
        target.write_text(new_content, encoding="utf-8")
    elif isinstance(breaker, DeleteBreaker):
        target = copy_root / breaker.path
        ensure_writable(target.parent)
        ensure_writable(target)
        target.unlink()
    elif isinstance(breaker, RenameBreaker):
        src = copy_root / breaker.src
        dst = copy_root / breaker.dst
        ensure_writable(src.parent)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    else:
        raise ValueError(f"apply_breaker called on non-executable breaker: {breaker!r}")


# --------------------------------------------------------------------------
# Dynamic judgement (SS4.2 D-0..D-4)
# --------------------------------------------------------------------------

def run_dynamic_case(repo_root: Path, ac: ACBlock, breaker, breaker_index: int, repeat: int, timeout: int) -> CaseResult:
    verdicts = []
    details = []
    snippet = ""

    for rep in range(repeat):
        with tempfile.TemporaryDirectory(prefix="breaker-b-") as b_dir, \
                tempfile.TemporaryDirectory(prefix="breaker-m-") as m_dir, \
                tempfile.TemporaryDirectory(prefix="breaker-env-") as env_dir:
            b_root = Path(b_dir) / "copy"
            m_root = Path(m_dir) / "copy"
            try:
                make_copy(repo_root, b_root)
                make_copy(repo_root, m_root)
            except Exception as exc:  # noqa: BLE001 -- per-AC isolation (SS1.11)
                return CaseResult("INVALID/internal", f"copy failed: {exc}", breaker_index)

            if not check_pnpm_workspace_layout(repo_root, b_root) or not check_pnpm_workspace_layout(repo_root, m_root):
                return CaseResult(
                    "UNSUPPORTED/dependency-layout",
                    "a dependency symlink in the copy resolves outside the sandbox "
                    "(pnpm workspace layout) -- refusing to report a possibly-wrong GUARDED",
                    breaker_index,
                )

            env_b = build_sample_env(Path(env_dir) / "b")
            env_m = build_sample_env(Path(env_dir) / "m")
            build_git_env(env_b, repo_root, b_root)
            build_git_env(env_m, repo_root, m_root)

            b_out, b_code, b_timeout, b_limit = run_command(ac.verify, b_root, env_b, timeout)
            if b_limit:
                return CaseResult("INVALID/output-limit", "baseline output exceeded 8MB", breaker_index)
            if b_timeout:
                verdicts.append("INVALID/timeout")
                details.append(f"rep{rep}: baseline timed out after {timeout}s")
                continue
            if b_code != 0:
                verdicts.append("BASELINE-RED")
                details.append(f"rep{rep}: baseline exit={b_code}")
                if not snippet:
                    snippet = "\n".join(b_out.splitlines()[:3])
                continue

            try:
                apply_breaker(m_root, breaker)
            except Exception as exc:  # noqa: BLE001
                return CaseResult("INVALID/internal", f"apply breaker failed: {exc}", breaker_index)

            m_out, m_code, m_timeout, m_limit = run_command(ac.verify, m_root, env_m, timeout)
            if m_limit:
                return CaseResult("INVALID/output-limit", "mutant output exceeded 8MB", breaker_index)
            if m_timeout:
                verdicts.append("INVALID/timeout")
                details.append(f"rep{rep}: mutant timed out after {timeout}s")
                continue
            if not snippet:
                snippet = "\n".join(m_out.splitlines()[:3])
            if m_code == 0:
                verdicts.append("VACUOUS")
                details.append(f"rep{rep}: mutant exit=0 (Verify did not react to Breaker)")
                continue
            if ac.expect_red not in m_out:
                hint = detect_forbidden_hint(m_out)
                msg = f"rep{rep}: Expect-red literal not found in mutant output"
                if hint:
                    msg += (
                        f" (hint: output matches a generic failure pattern '{hint}' -- "
                        f"likely a collection/compile error, not the targeted assertion)"
                    )
                verdicts.append("INVALID/mismatch")
                details.append(msg)
                continue
            if ac.expect_red in b_out:
                verdicts.append("INVALID/loose-signature")
                details.append(f"rep{rep}: Expect-red literal was already present in baseline output")
                continue
            verdicts.append("GUARDED")
            details.append(f"rep{rep}: guarded (mutant exit={m_code})")

    if not verdicts:
        return CaseResult("INVALID/internal", "no repetitions completed", breaker_index, snippet)
    if len(set(verdicts)) > 1:
        return CaseResult(
            "INCONCLUSIVE/flaky",
            f"judgement differed across {repeat} repeats: " + "; ".join(details),
            breaker_index, snippet,
        )
    return CaseResult(verdicts[0], "; ".join(details), breaker_index, snippet)


def combine_case_results(cases: list) -> tuple:
    if not cases:
        return "INVALID/field-count", "no breaker entries", ""
    n_guarded = sum(1 for c in cases if c.verdict == "GUARDED")
    if n_guarded == len(cases):
        detail = "; ".join(f"breaker#{c.breaker_index}: {c.detail}" for c in cases)
        snippet = cases[0].snippet
        return "GUARDED", detail, snippet
    failing = [c for c in cases if c.verdict != "GUARDED"]
    first = failing[0]
    detail = f"{n_guarded}/{len(cases)} breakers GUARDED; breaker#{first.breaker_index} {first.verdict}: {first.detail}"
    return first.verdict, detail, first.snippet or cases[0].snippet


# --------------------------------------------------------------------------
# Per-AC evaluation
# --------------------------------------------------------------------------

def evaluate_ac(repo_root: Path, ac: ACBlock, repeat: int, timeout: int) -> dict:
    base = {"ac_id": ac.ac_id, "scenarios": ac.scenario_count, "breakers": len(ac.breakers),
            "needs_observation_update": False, "observed_hint": None}

    if ac.parse_errors:
        msg = "; ".join(f"L{e.line}: {e.message}" for e in ac.parse_errors)
        return {**base, "verdict": "INVALID/field-count", "detail": msg}

    na_entries = [b for b in ac.breakers if isinstance(b, NABreaker)]
    err_entries = [b for b in ac.breakers if isinstance(b, BreakerParseError)]
    real_entries = [b for b in ac.breakers if isinstance(b, (ReplaceBreaker, DeleteBreaker, RenameBreaker))]

    if err_entries:
        msg = "; ".join(f"L{e.line}: {e.message}" for e in err_entries)
        return {**base, "verdict": "INVALID/breaker-syntax", "detail": msg}

    if na_entries and real_entries:
        return {**base, "verdict": "INVALID/mixed-na-breaker",
                "detail": "cannot mix 'Breaker: N/A' with a real Breaker in the same AC block"}

    if na_entries:
        reason = na_entries[0].reason
        return {**base, "verdict": "UNGUARDED", "detail": f"N/A — {reason}", "na_reason": reason}

    if ac.verify is None:
        return {**base, "verdict": "INVALID/field-count", "detail": "missing Verify"}

    # Design order is S-1/S-2/S-3 (per breaker) THEN E-1..E-6 (SS4.2). A breaker
    # that is e.g. self-referential must be reported as such even when the
    # shared Expect-red literal would also fail an E-check -- so the block-level
    # E-1..E-5 check on Expect-red is only run (and cached) once at least one
    # breaker has cleared its S-checks, not unconditionally up front.
    case_results = []
    expect_red_check = None
    expect_red_checked = False
    for idx, breaker in enumerate(real_entries, start=1):
        s_check = check_breaker_static(repo_root, breaker)
        if s_check:
            code, msg = s_check
            case_results.append(CaseResult(code, msg, idx))
            continue
        if not expect_red_checked:
            expect_red_check = check_expect_red(ac.expect_red, ac.verify, repo_root)
            expect_red_checked = True
        if expect_red_check:
            code, msg = expect_red_check
            case_results.append(CaseResult(code, msg, idx))
            continue
        e6 = check_e6(ac.expect_red, breaker)
        if e6:
            code, msg = e6
            case_results.append(CaseResult(code, msg, idx))
            continue
        try:
            case_results.append(run_dynamic_case(repo_root, ac, breaker, idx, repeat, timeout))
        except Exception as exc:  # noqa: BLE001 -- SS1.11: one AC's crash must not kill the run
            case_results.append(CaseResult("INVALID/internal", f"unexpected error: {exc}", idx))

    verdict, detail, snippet = combine_case_results(case_results)
    unprotected = max(0, ac.scenario_count - len(ac.breakers))
    needs_obs = bool(ac.observed_raw and ac.observed_raw.strip() == UNOBSERVED_MARKER)

    return {
        **base,
        "verdict": verdict,
        "detail": detail,
        "unprotected": unprotected,
        "needs_observation_update": needs_obs,
        "observed_hint": snippet if needs_obs else None,
    }


# --------------------------------------------------------------------------
# --require-coverage (SS5)
# --------------------------------------------------------------------------

BASE_SHA_HEX_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")

PY_TEST_NAME_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)")
JS_TEST_NAME_RE = re.compile(r"""^\s*(?:it|test)\s*(?:\.\w+)?\s*\(\s*['"`](.+?)['"`]""")
GO_TEST_NAME_RE = re.compile(r"^func\s+(Test\w+)\s*\(")


def run_git(args: list, cwd: Path):
    try:
        proc = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def check_coverage(repo_root: Path, plan_text: str, blocks: list, results: list) -> dict:
    found, sha = find_base_sha(plan_text)
    if not found or not sha or not BASE_SHA_HEX_RE.match(sha):
        return {
            "status": "INVALID/no-base-sha", "exit": 2, "detected_count": 0,
            "message": "plan file is missing a valid '**Base-SHA:** <40- or 64-char hex>' line in its preamble",
        }

    code, _ = run_git(["cat-file", "-e", f"{sha}^{{commit}}"], repo_root)
    if code != 0:
        return {
            "status": "INVALID/no-base-sha", "exit": 2, "detected_count": 0,
            "message": f"Base-SHA {sha} does not resolve to a commit in {repo_root}",
        }

    code, _ = run_git(["merge-base", "--is-ancestor", sha, "HEAD"], repo_root)
    if code != 0:
        return {
            "status": "STALE-BASE", "exit": 1, "detected_count": 0,
            "message": f"Base-SHA {sha} is not an ancestor of HEAD -- plan is stale "
                       f"(not auto-refreshed; update Base-SHA and re-run)",
        }

    _, out = run_git(["diff", "-z", "--name-only", sha, "--"], repo_root)
    changed_files = [f for f in out.split("\0") if f]
    changed_test_files = [f for f in changed_files if is_test_path(Path(f))]

    detected = []
    for f in changed_test_files:
        _, diff_out = run_git(["diff", "-U0", sha, "--", f], repo_root)
        for line in diff_out.split("\n"):
            if not line.startswith("+") or line.startswith("+++"):
                continue
            content = line[1:]
            m = PY_TEST_NAME_RE.match(content)
            if m:
                detected.append(m.group(1))
                continue
            m = JS_TEST_NAME_RE.match(content)
            if m:
                detected.append(m.group(1))
                continue
            m = GO_TEST_NAME_RE.match(content)
            if m:
                detected.append(m.group(1))
                continue

    detected = sorted(set(detected))
    guarded_ids = {r["ac_id"] for r in results if r["verdict"] == "GUARDED"}
    guarded_text = "\n".join(b.raw_text for b in blocks if b.ac_id in guarded_ids)

    missing = [name for name in detected if not re.search(rf"\b{re.escape(name)}\b", guarded_text)]
    status = "MISSING-COVERAGE" if missing else "OK"
    return {
        "status": status, "exit": 1 if missing else 0,
        "detected_count": len(detected), "detected": detected, "missing": missing,
    }


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def summarize(results: list) -> dict:
    counts = {"GUARDED": 0, "VACUOUS": 0, "INVALID": 0, "BASELINE-RED": 0,
              "UNGUARDED": 0, "INCONCLUSIVE": 0, "UNSUPPORTED": 0}
    for r in results:
        v = r["verdict"]
        if v.startswith("INVALID"):
            counts["INVALID"] += 1
        elif v.startswith("INCONCLUSIVE"):
            counts["INCONCLUSIVE"] += 1
        elif v.startswith("UNSUPPORTED"):
            counts["UNSUPPORTED"] += 1
        elif v in counts:
            counts[v] += 1
        else:
            counts[v] = counts.get(v, 0) + 1
    return counts


def render_text(results, coverage_result, waivers_ok, accept_ids, unguarded_ids, exit_code) -> str:
    lines = list(GUARANTEE_LINES)
    lines.append("")
    lines.append("AC-ID | 판정 | 사유/힌트 | scenarios n / breakers m")
    for r in results:
        note = ""
        if r["scenarios"] > r["breakers"]:
            note = f" → {r['scenarios'] - r['breakers']}개 미보호"
        lines.append(f"{r['ac_id']} | {r['verdict']} | {r['detail']} | {r['scenarios']}/{r['breakers']}{note}")

    lines.append("")
    counts = summarize(results)
    lines.append("집계: " + " ".join(f"{k}={v}" for k, v in counts.items()))

    if accept_ids or unguarded_ids:
        if waivers_ok:
            waived = ", ".join(sorted(unguarded_ids)) or "-"
            lines.append(f"waiver: PASS-WITH-WAIVERS ({waived})")
        else:
            missing_accept = unguarded_ids - accept_ids
            extra_accept = accept_ids - unguarded_ids
            lines.append("waiver 불일치:")
            if missing_accept:
                lines.append(f"  UNGUARDED 이나 --accept-unguarded 에 없음: {', '.join(sorted(missing_accept))}")
            if extra_accept:
                lines.append(f"  --accept-unguarded 에 있으나 UNGUARDED 아님: {', '.join(sorted(extra_accept))}")

    needs_obs = [r for r in results if r.get("needs_observation_update")]
    if needs_obs:
        lines.append("")
        lines.append("Observed 갱신 필요 (계획서 'Observed:' 에 아래를 붙여넣으세요):")
        for r in needs_obs:
            lines.append(f"  {r['ac_id']}:")
            for hl in (r.get("observed_hint") or "(출력 없음)").split("\n"):
                lines.append(f"    {hl}")

    if coverage_result is not None:
        lines.append("")
        lines.append(f"--require-coverage: 탐지한 신규 테스트 {coverage_result.get('detected_count', 0)}개")
        if coverage_result["status"] == "INVALID/no-base-sha":
            lines.append(f"  INVALID/no-base-sha: {coverage_result['message']}")
        elif coverage_result["status"] == "STALE-BASE":
            lines.append(f"  STALE-BASE: {coverage_result['message']}")
        elif coverage_result.get("missing"):
            lines.append(f"  미등록 테스트: {', '.join(coverage_result['missing'])}")
        else:
            lines.append("  탐지된 신규 테스트 전부 GUARDED AC 블록에 등록됨")

    lines.append("")
    lines.append(f"종료 코드: {exit_code}")
    return "\n".join(lines)


def render_json(results, coverage_result, waivers_ok, accept_ids, unguarded_ids, exit_code) -> str:
    payload = {
        "guarantee": GUARANTEE_LINES,
        "results": results,
        "summary": summarize(results),
        "waivers": {
            "ok": waivers_ok,
            "accepted": sorted(accept_ids),
            "unguarded": sorted(unguarded_ids),
        },
        "coverage": coverage_result,
        "exit_code": exit_code,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="breaker.py",
        description=(
            "AC gate harness for plan-acc. For each AC block's Breaker mutation, checks "
            "that the declared Verify command reacts with the declared Expect-red literal "
            "signature on an isolated repo copy. GUARDED means the verification observed "
            "something -- it does not mean the verification observed the right thing."
        ),
    )
    p.add_argument("plan", help="path to the plan markdown file")
    p.add_argument(
        "--repo",
        required=True,
        help="project repo root (source and Git metadata execute from temp copies)",
    )
    p.add_argument("--require-coverage", action="store_true",
                    help="also verify that test functions added since Base-SHA are referenced by a GUARDED AC block")
    p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                    help=f"repetitions per breaker for flake detection (default {DEFAULT_REPEAT})")
    p.add_argument("--accept-unguarded", default="",
                    help="comma-separated AC IDs whose 'Breaker: N/A' waiver is accepted, e.g. T7,T12")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of the text table")
    return p


def main(argv=None) -> int:
    args = build_argparser().parse_args(argv)
    plan_path = Path(args.plan)
    repo_root = Path(args.repo)

    if not plan_path.is_file():
        print(f"error: plan file not found: {plan_path}", file=sys.stderr)
        return 2
    if not repo_root.is_dir():
        print(f"error: --repo is not a directory: {repo_root}", file=sys.stderr)
        return 2
    repo_root = repo_root.resolve()

    plan_text = plan_path.read_text(encoding="utf-8", errors="replace")
    try:
        blocks = parse_plan(plan_text)
    except Exception as exc:  # noqa: BLE001
        print(f"error: failed to parse plan: {exc}", file=sys.stderr)
        return 2

    if not blocks:
        print("error: no AC blocks found in plan (expected at least one '- **AC:**' block)", file=sys.stderr)
        return 2

    results = []
    for ac in blocks:
        try:
            results.append(evaluate_ac(repo_root, ac, args.repeat, DEFAULT_TIMEOUT))
        except Exception as exc:  # noqa: BLE001 -- SS1.11
            results.append({
                "ac_id": ac.ac_id, "verdict": "INVALID/internal", "detail": f"unexpected error: {exc}",
                "scenarios": ac.scenario_count, "breakers": len(ac.breakers),
                "needs_observation_update": False, "observed_hint": None,
            })

    accept_ids = {x.strip() for x in args.accept_unguarded.split(",") if x.strip()}
    unguarded_ids = {r["ac_id"] for r in results if r["verdict"] == "UNGUARDED"}
    waivers_ok = accept_ids == unguarded_ids

    gate_failed = False
    for r in results:
        v = r["verdict"]
        if v == "GUARDED":
            continue
        if v == "UNGUARDED" and waivers_ok:
            continue
        gate_failed = True

    exit_code = 1 if (gate_failed or not waivers_ok) else 0
    if any(r.get("needs_observation_update") for r in results):
        exit_code = max(exit_code, 1)

    coverage_result = None
    if args.require_coverage:
        coverage_result = check_coverage(repo_root, plan_text, blocks, results)
        exit_code = max(exit_code, coverage_result["exit"])

    if args.json:
        print(render_json(results, coverage_result, waivers_ok, accept_ids, unguarded_ids, exit_code))
    else:
        print(render_text(results, coverage_result, waivers_ok, accept_ids, unguarded_ids, exit_code))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
