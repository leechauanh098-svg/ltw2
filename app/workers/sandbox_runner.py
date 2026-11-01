import os
import sys
import time
import shutil
import tempfile
import subprocess
from dataclasses import dataclass

try:
    import resource
    HAS_RESOURCE_MODULE = True
except ImportError:
    HAS_RESOURCE_MODULE = False


@dataclass
class ExecutionResult:
    verdict: str            # "AC", "WA", "TLE", "MLE", "RE", "CE"
    stdout: str
    stderr: str
    execution_time_ms: int
    memory_used_kb: int


def _apply_posix_limits(cpu_time_sec: int, memory_limit_bytes: int):
    if not HAS_RESOURCE_MODULE:
        return
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_time_sec, cpu_time_sec + 1))
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))


def normalize_output(text: str) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return "\n".join(lines)


def run_testcase_in_sandbox(
    language: str,
    source_code: str,
    stdin_data: str,
    expected_output: str,
    time_limit_ms: int = 1500,
    memory_limit_kb: int = 65536,
) -> ExecutionResult:
    """
    Thực thi mã nguồn của học viên trong thư mục tạm cô lập với subprocess + timeout.
    Tương thích cả Windows (local MVP) và Linux (production).
    """
    temp_dir = tempfile.mkdtemp(prefix="judge_sandbox_")

    try:
        if language == "python":
            src_file = os.path.join(temp_dir, "solution.py")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)
            compile_cmd = None
            run_cmd = [sys.executable, "-I", "-B", src_file]
        elif language == "cpp":
            src_file = os.path.join(temp_dir, "solution.cpp")
            bin_file = os.path.join(temp_dir, "solution.exe" if os.name == "nt" else "solution")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write(source_code)
            compile_cmd = ["g++", "-O2", "-std=c++17", src_file, "-o", bin_file]
            run_cmd = [bin_file]
        else:
            return ExecutionResult("CE", "", f"Ngôn ngữ không hỗ trợ: {language}", 0, 0)

        if compile_cmd:
            try:
                comp_proc = subprocess.run(
                    compile_cmd,
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except FileNotFoundError:
                return ExecutionResult(
                    "CE", "", "Không tìm thấy trình biên dịch g++ trên máy chủ.", 0, 0
                )
            if comp_proc.returncode != 0:
                return ExecutionResult("CE", "", comp_proc.stderr[:2000], 0, 0)

        wall_timeout_sec = (time_limit_ms / 1000.0) + 0.5
        cpu_limit_sec = max(1, int(time_limit_ms / 1000) + 1)
        memory_limit_bytes = memory_limit_kb * 1024

        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONIOENCODING": "utf-8",
        }

        start_time = time.perf_counter()
        proc_kwargs = {
            "cwd": temp_dir,
            "input": stdin_data,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": wall_timeout_sec,
            "env": clean_env,
        }
        if HAS_RESOURCE_MODULE:
            proc_kwargs["preexec_fn"] = lambda: _apply_posix_limits(
                cpu_limit_sec, memory_limit_bytes
            )

        proc = subprocess.run(run_cmd, **proc_kwargs)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        peak_memory_kb = 12400  # Giá trị ước lượng mặc định trên Windows
        if HAS_RESOURCE_MODULE:
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            peak_memory_kb = int(usage.ru_maxrss)

        if elapsed_ms > time_limit_ms:
            return ExecutionResult("TLE", "", "Time Limit Exceeded", elapsed_ms, peak_memory_kb)

        if proc.returncode != 0:
            if "MemoryError" in proc.stderr or "bad_alloc" in proc.stderr or proc.returncode in (-9, 137):
                return ExecutionResult("MLE", "", "Memory Limit Exceeded", elapsed_ms, peak_memory_kb)
            return ExecutionResult("RE", proc.stdout[:1000], proc.stderr[:2000], elapsed_ms, peak_memory_kb)

        actual_out = normalize_output(proc.stdout)
        expected_out = normalize_output(expected_output)

        if actual_out == expected_out:
            return ExecutionResult("AC", proc.stdout[:1000], "", elapsed_ms, peak_memory_kb)
        else:
            return ExecutionResult("WA", proc.stdout[:1000], "", elapsed_ms, peak_memory_kb)

    except subprocess.TimeoutExpired:
        return ExecutionResult("TLE", "", "Time Limit Exceeded (Quá thời gian giới hạn)", time_limit_ms, 0)
    except Exception as exc:
        return ExecutionResult("RE", "", str(exc), 0, 0)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
