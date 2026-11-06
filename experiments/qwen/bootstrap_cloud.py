"""Permission-gated, task-local Linux bootstrap. Never invoked by tests or import.

For an interactive free GPU notebook only. No account creation, billing changes,
Drive mounts, public tunnel, background persistence or system package changes.
"""

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from urllib.request import urlopen

from .portable import ROOT, exclusive_json, resources

RUNTIME_URL = "https://github.com/ollama/ollama/releases/download/v0.40.14/ollama-linux-amd64.tar.zst"
RUNTIME_SHA256 = "993e83d08c3d13d17c55009a3e2664c8a25445e644aec3a68bef5abb6abce67d"
RUNTIME_BYTES = 1525335029


def approvals(args):
    if not all(
        (
            args.approved_runtime,
            args.approved_weights,
            args.approved_synthetic_transfer,
            args.free_runtime_confirmed,
        )
    ):
        raise ValueError(
            "Explicit environment, installation, weights and synthetic transfer authorization required"
        )


def ensure_port_free():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 11435))
    except OSError:
        raise ValueError(
            "Port 11435 is occupied; do not use an existing daemon"
        ) from None


def owns_listener(pid):
    """Linux bootstrap: the actual serving process must own the listening socket."""
    try:
        inodes = set()
        for line in Path("/proc/net/tcp").read_text().splitlines()[1:]:
            fields = line.split()
            if fields[1] == "0100007F:2CAB" and fields[3] == "0A":
                inodes.add(fields[9])
        descriptors = set()
        for entry in Path(f"/proc/{pid}/fd").iterdir():
            try:
                descriptors.add(entry.readlink().as_posix())
            except FileNotFoundError:
                continue
        return any(f"socket:[{inode}]" in descriptors for inode in inodes)
    except OSError:
        return False


def require_owned_server(server):
    if server.poll() is not None or not owns_listener(server.pid):
        raise ValueError("Dedicated server ownership was not verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in (
        "approved-runtime",
        "approved-weights",
        "approved-synthetic-transfer",
        "free-runtime-confirmed",
    ):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args()
    approvals(args)
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required")
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise ValueError("This portable bootstrap targets Linux x86_64 GPU notebooks")
    status = resources()
    if not status["qwen35_9b_gpu_candidate"]:
        print(json.dumps(status, indent=2))
        raise ValueError(
            "Insufficient or unmeasured free GPU/RAM/disk; no download started"
        )
    ensure_port_free()
    root = ROOT / ".local/cloud-runtime"
    root.mkdir(parents=True, exist_ok=False)
    exclusive_json(root / "preflight.json", status)
    deps = root / "python-deps"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(deps),
            "jsonschema==4.26.0",
            "referencing==0.37.0",
            "zstandard==0.25.0",
        ],
        check=True,
        timeout=300,
    )
    sys.path.insert(0, str(deps))
    import zstandard

    package = root / "ollama.tar.zst"
    digest = hashlib.sha256()
    download_started = time.monotonic()
    received = 0
    with urlopen(RUNTIME_URL, timeout=60) as response, package.open("xb") as stream:
        while chunk := response.read(1048576):
            received += len(chunk)
            if received > RUNTIME_BYTES or time.monotonic() - download_started > 600:
                raise ValueError("Runtime archive size/time budget exceeded")
            digest.update(chunk)
            stream.write(chunk)
    if received != RUNTIME_BYTES or digest.hexdigest() != RUNTIME_SHA256:
        raise ValueError(
            "Official runtime checksum mismatch; not extracted or executed"
        )
    with (
        package.open("rb") as stream,
        zstandard.ZstdDecompressor().stream_reader(stream) as reader,
        tarfile.open(fileobj=reader, mode="r|") as archive,
    ):
        archive.extractall(root / "ollama", filter="data")
    binary = root / "ollama/bin/ollama"
    environment = dict(os.environ)
    environment.update(
        OLLAMA_HOST="127.0.0.1:11435",
        OLLAMA_MODELS=str(root / "models"),
        OLLAMA_NO_CLOUD="1",
        OLLAMA_NUM_PARALLEL="1",
        OLLAMA_MAX_LOADED_MODELS="1",
        OLLAMA_MAX_QUEUE="1",
        OLLAMA_KEEP_ALIVE="0",
        OLLAMA_DEBUG="0",
        OLLAMA_CONTEXT_LENGTH="16384",
        CUDA_VISIBLE_DEVICES=str(
            next(
                gpu["index"]
                for gpu in status["gpus"]
                if gpu["free_bytes"] >= 10 * 1024**3
            )
        ),
        PYTHONPATH=str(deps) + os.pathsep + str(ROOT),
    )
    # Interactive bounded session. Server is stopped in finally; no public API.
    ensure_port_free()
    with (root / "server.log").open("xb") as log:
        server = subprocess.Popen(
            [str(binary), "serve"], env=environment, stdout=log, stderr=log, cwd=ROOT
        )
        try:
            ready = False
            for _ in range(60):
                if server.poll() is not None:
                    break
                try:
                    with urlopen(
                        "http://127.0.0.1:11435/api/version", timeout=1
                    ) as response:
                        ready = json.load(response).get("version") == "0.40.14"
                    if ready:
                        require_owned_server(server)
                        break
                except OSError:
                    pass
                time.sleep(1)
            if not ready:
                raise ValueError(
                    "Dedicated Ollama failed readiness; inspect local technical log"
                )
            model = "qwen3.5:9b-q4_K_M"
            require_owned_server(server)
            subprocess.run(
                [str(binary), "pull", model], env=environment, check=True, timeout=900
            )
            require_owned_server(server)
            commands = [
                [
                    "experiments.qwen.portable",
                    "matrix",
                    "--output",
                    ".local/qwen-runs/cloud-matrix",
                    "--sampler",
                    "matched",
                ],
            ]
            for module, *arguments in commands:
                subprocess.run(
                    [sys.executable, "-B", "-m", module, *arguments],
                    env=environment,
                    cwd=ROOT,
                    check=True,
                )
            for profile in ("product", "experimental"):
                require_owned_server(server)
                config = (
                    f".local/qwen-runs/cloud-matrix/qwen35-9b-{profile}-matched.json"
                )
                lock = f".local/qwen-runs/cloud-9b-{profile}.lock.json"
                shared = [
                    "--config",
                    config,
                    "--allow-local-inference",
                    "--synthetic-only",
                ]
                subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "experiments.qwen.run",
                        "lock",
                        *shared,
                        "--output",
                        lock,
                    ],
                    env=environment,
                    cwd=ROOT,
                    check=True,
                    timeout=120,
                )
                # Same four inputs for both prompts, technical results remain
                # available even when validation returns exit 1.
                require_owned_server(server)
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "experiments.qwen.run",
                        "run",
                        *shared,
                        "--lock",
                        lock,
                        "--output",
                        f".local/qwen-runs/cloud-9b-{profile}",
                        "--case",
                        "D-conflict",
                        "--case",
                        "K-conditions",
                        "--case",
                        "S-compatible",
                        "--case",
                        "U-insufficient",
                    ],
                    env=environment,
                    cwd=ROOT,
                    check=False,
                    timeout=600,
                )
                if result.returncode not in {0, 1}:
                    raise ValueError(
                        "Harness failed; preserve diagnostics before continuing"
                    )
                # Do not send another series after a model timeout/uncertain cancellation.
                summary = json.loads(
                    (
                        ROOT / f".local/qwen-runs/cloud-9b-{profile}/diagnostics.json"
                    ).read_text("utf-8")
                )
                if any(
                    (r["error"] or {}).get("code") == "timeout"
                    for r in summary["records"]
                ):
                    break
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
