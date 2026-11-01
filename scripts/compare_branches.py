"""Reproduce the Task 5 comparison in isolated, pinned Git exports.

Does not checkout branches, modify another worktree, read real .env files, or
contact market services. uv (or pip) installs each snapshot's own requirements.
"""

import argparse
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMITS = {"codex": "68ad48e", "antigravity": "6ef049a", "deepseek": "0307b44"}


def export_snapshots(base):
    manifest = base / "snapshots.json"
    if manifest.exists():
        if json.loads(manifest.read_text()) != COMMITS:
            raise ValueError("Snapshot manifest does not match the pinned commits")
        if any((base / branch / ".git").exists() for branch in COMMITS):
            raise ValueError("Use exported snapshots, not active Git worktrees")
        return
    if any(base.iterdir()):
        raise ValueError("Snapshot directory must be empty")
    for branch, commit in COMMITS.items():
        target = base / branch
        target.mkdir()
        archive = subprocess.check_output(
            ["git", "archive", "--format=tar", commit], cwd=ROOT
        )
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(target, filter="data")
    manifest.write_text(json.dumps(COMMITS, indent=2) + "\n")


def evaluate(branch, base):
    directory = base / branch
    # Each run starts with an empty synthetic DB, even when reusing installed venvs.
    (directory / "evaluation.sqlite3").unlink(missing_ok=True)
    python = directory / ".venv" / "bin" / "python"
    env = os.environ.copy()
    env.update(
        DJANGO_DEBUG="true",
        DJANGO_SECRET_KEY="synthetic-comparison-development-key",
        DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,testserver",
        DJANGO_DB_ENGINE="sqlite",
        SQLITE_PATH=str(directory / "evaluation.sqlite3"),
        TINKOFF_TOKEN="",
        COMPARISON_BRANCH=branch,
        COMPARISON_PROBES_OUTPUT=str(directory / "probes.json"),
    )
    result = {"commit": COMMITS[branch], "steps": {}}

    def run(label, command, timeout=180):
        start = time.perf_counter()
        process = subprocess.run(
            [str(arg) for arg in command],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = process.stdout + process.stderr
        (directory / f"comparison-{label}.log").write_text(output)
        result["steps"][label] = {
            "exit_code": process.returncode,
            "wall_seconds": round(time.perf_counter() - start, 3),
        }
        return process.returncode, output

    if not python.exists():
        code, _ = run("venv", [sys.executable, "-m", "venv", ".venv"])
        if code:
            return result
    uv = shutil.which("uv")
    install = (
        [uv, "pip", "install", "--system-certs", "--python", str(python)]
        if uv
        else [str(python), "-m", "pip", "install"]
    )
    code, _ = run("install", [*install, "-r", "requirements.txt"])
    if code:
        return result
    # Instrumentation only; does not change a branch's declared dependencies.
    code, _ = run("coverage-tool", [*install, "coverage==7.17.0"])
    if code:
        return result
    _, versions = run(
        "versions",
        [
            python,
            "-c",
            "import importlib.metadata,json; print(json.dumps({d.metadata['Name']:d.version for d in importlib.metadata.distributions()},sort_keys=True))",
        ],
    )
    result["installed"] = json.loads(versions)
    source = ["config", "dashboard", "user"]
    source.extend(
        name for name in ("investing", "investments") if (directory / name).is_dir()
    )
    _, output = run(
        "tests",
        [
            python,
            "-m",
            "coverage",
            "run",
            "--source=" + ",".join(source),
            "--omit=*/migrations/*,*/test*,*/tests/*",
            "manage.py",
            "test",
            "--noinput",
        ],
    )
    count = re.search(r"Ran (\d+) tests? in ([\d.]+)s", output)
    if count:
        skipped = re.search(r"skipped=(\d+)", output)
        result["tests"] = {
            "run": int(count[1]),
            "reported_seconds": float(count[2]),
            "skipped": int(skipped[1]) if skipped else 0,
            "ok": bool(re.search(r"^OK\b", output, re.M)),
        }
    run(
        "coverage-json",
        [python, "-m", "coverage", "json", "-o", "comparison-coverage.json"],
    )
    coverage_path = directory / "comparison-coverage.json"
    if coverage_path.exists():
        result["coverage"] = json.loads(coverage_path.read_text())["totals"]
    run("check", [python, "manage.py", "check"])
    run(
        "migration-state",
        [python, "manage.py", "makemigrations", "--check", "--dry-run"],
    )
    code, _ = run("migrate", [python, "manage.py", "migrate", "--noinput"])
    if code:
        return result
    run(
        "probes",
        [
            python,
            "manage.py",
            "shell",
            "-c",
            f"import runpy; runpy.run_path({str(ROOT / 'scripts' / 'comparison_probes.py')!r})",
        ],
    )
    if (directory / "probes.json").exists():
        result["probes"] = json.loads((directory / "probes.json").read_text())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (directory / "comparison-server.log").open("w") as log:
        server = subprocess.Popen(
            [str(python), "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
            cwd=directory,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for attempt in range(100):
                try:
                    connection = HTTPConnection("127.0.0.1", port, timeout=1)
                    connection.request("GET", "/")
                    response = connection.getresponse()
                    response.read()
                    connection.close()
                    if response.status == 200:
                        break
                except OSError:
                    pass
                if server.poll() is not None:
                    break
                time.sleep(0.1)
            result["http"] = {}
            for path in ("/", "/api/v1/shares/"):
                connection = HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request("GET", path)
                response = connection.getresponse()
                response.read()
                result["http"][path] = response.status
                connection.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "audit" / "comparison.json"
    )
    args = parser.parse_args()
    base = args.snapshot_root or Path(tempfile.mkdtemp(prefix="investing-comparison-"))
    base.mkdir(parents=True, exist_ok=True)
    export_snapshots(base)
    with ThreadPoolExecutor(max_workers=3) as pool:
        values = list(pool.map(lambda name: (name, evaluate(name, base)), COMMITS))
    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "database": "SQLite",
        "source": "pinned git archive exports",
        "market": "local fixture only; no real market token",
        "branches": dict(values),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for name, item in values:
        print(
            name,
            item.get("tests"),
            "http:",
            item.get("http"),
            "coverage:",
            round(item.get("coverage", {}).get("percent_covered", 0), 2),
        )
    print("Snapshots and command logs:", base)
    print("Saved:", args.output)
    if any(
        not item.get("tests", {}).get("ok")
        or any(step["exit_code"] for step in item["steps"].values())
        or len(item.get("probes", {})) != 11
        or any("probe_error" in probe for probe in item.get("probes", {}).values())
        or item.get("http") != {"/": 200, "/api/v1/shares/": 200}
        for _, item in values
    ):
        raise SystemExit("Comparison run incomplete; inspect saved results and logs")


if __name__ == "__main__":
    main()
