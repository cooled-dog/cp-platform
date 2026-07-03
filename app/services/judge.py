import asyncio
import os
import tempfile
import shutil
import time
from dataclasses import dataclass
from typing import Optional
from app.models.models import Language, Verdict

@dataclass
class JudgeResult:
    verdict: Verdict
    time_ms: Optional[int] = None
    error_message: Optional[str] = None


IMAGES = {
    Language.CPP:    "gcc:13",
    Language.PYTHON: "python:3.12-slim",
}

COMPILE_CMDS = {
    Language.CPP:    "g++ -O2 -o /sandbox/solution /sandbox/solution.cpp 2>&1",
    Language.PYTHON: None,
}

RUN_CMDS = {
    Language.CPP:    "/sandbox/solution",
    Language.PYTHON: "python3 /sandbox/solution.py",
}

SOURCE_FILES = {
    Language.CPP:    "solution.cpp",
    Language.PYTHON: "solution.py",
}


async def _run(cmd: str, timeout: float, stdin: str = "") -> tuple[int, str, str]:
    """Run a shell command asynchronously."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin.encode()),
            timeout=timeout,
        )
        return proc.returncode, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return -1, "", "TIMEOUT"


async def judge_submission(
    code: str,
    language: Language,
    test_cases: list[tuple[str, str]],
    time_limit_ms: int,
    memory_limit_mb: int,
) -> JudgeResult:
    tmpdir = tempfile.mkdtemp(prefix="judge_")
    try:
        return await _judge(code, language, test_cases, time_limit_ms, memory_limit_mb, tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def _judge(code, language, test_cases, time_limit_ms, memory_limit_mb, tmpdir):

    source_path = os.path.join(tmpdir, SOURCE_FILES[language])
    with open(source_path, "w") as f:
        f.write(code)

    image = IMAGES[language]


    if COMPILE_CMDS[language]:
        cmd = (
            f"docker run --rm --network none "
            f"-v {tmpdir}:/sandbox "
            f"{image} sh -c '{COMPILE_CMDS[language]}'"
        )
        retcode, stdout, stderr = await _run(cmd, timeout=30.0)
        if retcode != 0:
            return JudgeResult(verdict=Verdict.CE, error_message=(stdout + stderr)[:2000])


    time_limit_sec = time_limit_ms / 1000.0
    max_time_ms = 0

    for input_data, expected_output in test_cases:
        cmd = (
            f"docker run -i --rm --network none "
            f"--memory {memory_limit_mb}m "
            f"--cpus 0.5 "
            f"--pids-limit 50 "
            f"--read-only "
            f"-v {tmpdir}:/sandbox:ro "
            f"{image} {RUN_CMDS[language]}"
        )
        start = time.monotonic()
        retcode, stdout, stderr = await _run(cmd, timeout=time_limit_sec + 1.0, stdin=input_data)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        max_time_ms = max(max_time_ms, elapsed_ms)

        if stderr == "TIMEOUT" or elapsed_ms > time_limit_ms:
            return JudgeResult(verdict=Verdict.TLE, time_ms=elapsed_ms)
        if retcode == 137:
            return JudgeResult(verdict=Verdict.MLE, time_ms=elapsed_ms)
        if retcode != 0:
            return JudgeResult(verdict=Verdict.RE, time_ms=elapsed_ms, error_message=stderr[:2000])
        if stdout.strip() != expected_output.strip():
            return JudgeResult(verdict=Verdict.WA, time_ms=elapsed_ms)

    return JudgeResult(verdict=Verdict.AC, time_ms=max_time_ms)