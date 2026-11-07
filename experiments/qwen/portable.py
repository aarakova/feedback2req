"""Stdlib-only resource check, comparison matrix and clean-source portable bundle."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
F2_COMMIT = "4c62684e7769d2c3a71de3264aa15e954a1262d0"
GIB = 1024**3


def capture(command):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=True, cwd=ROOT
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def resources():
    available = None
    if Path("/proc/meminfo").is_file():
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
    elif os.name == "nt":
        raw = capture(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory",
            ]
        )
        if raw and raw.isdecimal():
            available = int(raw) * 1024
    proc_available = available
    cgroup_limit, cgroup_used = None, None
    for limit_path, used_path in (
        ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
        (
            "/sys/fs/cgroup/memory/memory.limit_in_bytes",
            "/sys/fs/cgroup/memory/memory.usage_in_bytes",
        ),
    ):
        try:
            limit_text = Path(limit_path).read_text().strip()
            used_text = Path(used_path).read_text().strip()
            if limit_text.isdecimal() and used_text.isdecimal():
                cgroup_limit, cgroup_used = int(limit_text), int(used_text)
                group_available = max(0, cgroup_limit - cgroup_used)
                available = (
                    min(available, group_available)
                    if available is not None
                    else group_available
                )
                break
        except OSError:
            continue
    gpu_text = capture(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    gpus = []
    if gpu_text:
        for line in gpu_text.splitlines():
            values = [s.strip() for s in line.split(",")]
            if len(values) == 5:
                try:
                    gpus.append(
                        {
                            "index": int(values[0]),
                            "name": values[1],
                            "total_bytes": int(values[2]) * 1048576,
                            "free_bytes": int(values[3]) * 1048576,
                            "driver": values[4],
                        }
                    )
                except ValueError:
                    continue
    free_disk = shutil.disk_usage(ROOT).free
    gpu_ok = any(g["free_bytes"] >= 10 * GIB for g in gpus)
    gpu_candidate = bool(
        gpu_ok and available and available >= 8 * GIB and free_disk >= 16 * GIB
    )
    cpu_candidate = bool(available and available >= 16 * GIB and free_disk >= 16 * GIB)
    return {
        "mode": "resource_preflight_no_inference",
        "measured_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_threads": os.cpu_count(),
        "available_ram_bytes": available,
        "proc_mem_available_bytes": proc_available,
        "cgroup_memory_limit_bytes": cgroup_limit,
        "cgroup_memory_current_bytes": cgroup_used,
        "disk_free_bytes": free_disk,
        "gpus": gpus,
        "qwen35_9b_gpu_candidate": gpu_candidate,
        "qwen35_9b_cpu_candidate": cpu_candidate,
        "thresholds": {
            "gpu_free_bytes": 10 * GIB,
            "gpu_host_ram_free_bytes": 8 * GIB,
            "cpu_ram_free_bytes": 16 * GIB,
            "disk_free_bytes": 16 * GIB,
        },
        "limitations": "Planning gates, not measured model minima; validate driver/runtime/model support separately. No account/quota authorization or GPU reservation is implied.",
    }


def matrix(sampler="matched", timeout=90):
    if sampler not in {"matched", "recommended"}:
        raise ValueError("unknown_sampler")
    configs = {}
    for filename in ("qwen3-4b.json", "qwen35-9b.json"):
        base = json.loads((Path(__file__).with_name(filename)).read_text("utf-8"))
        for profile in ("product", "experimental"):
            cfg = json.loads(json.dumps(base))
            cfg["prompt_profile"] = profile
            cfg["timeout_seconds"] = timeout
            cfg["run_timeout_seconds"] = 900
            cfg["options"].update(num_ctx=16384, num_gpu=99)
            if sampler == "matched":
                cfg["options"].update(presence_penalty=0, repeat_penalty=1)
            name = filename[:-5] + "-" + profile + "-" + sampler
            configs[name] = cfg
    return configs


def exclusive_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def local_output(value):
    output = Path(value).resolve()
    allowed = (ROOT / ".local/qwen-runs").resolve()
    if not output.is_relative_to(allowed) or output == allowed:
        raise ValueError("output_must_be_ignored_task_child")
    return output


def bundle(output):
    """Export committed allowlisted source, with no working-tree/private files."""
    paths = [
        "experiments",
        "ai",
        "evals/ai",
        "docs/contracts/ai",
        "docs/AI_CONTRACTS.md",
        "docs/AI_VALIDATION.md",
        "docs/REQUIREMENTS.md",
        "scripts/validate_ai_contracts.py",
    ]
    if capture(["git", "status", "--porcelain", "--", *paths]):
        raise ValueError("commit_bundle_sources_first")
    revision = capture(["git", "rev-parse", "HEAD"])
    if not revision:
        raise ValueError("git_source_required")
    files = capture(["git", "ls-tree", "-r", "--name-only", revision, "--", *paths])
    output = local_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with ZipFile(output, "x", ZIP_DEFLATED) as archive:
        for filename in files.splitlines():
            # All entries are explicit committed source; no .local, env or model paths.
            data = subprocess.run(
                ["git", "show", revision + ":" + filename],
                capture_output=True,
                check=True,
                cwd=ROOT,
            ).stdout
            hashes[filename] = hashlib.sha256(data).hexdigest()
            archive.writestr(filename, data)
        archive.writestr(
            "BUNDLE-MANIFEST.json",
            json.dumps(
                {
                    "mode": "portable_synthetic_source_no_inference",
                    "source_provenance": "git_object_export",
                    "revision": revision,
                    "f2_reference_commit": F2_COMMIT,
                    "sha256": hashes,
                },
                indent=2,
            ),
        )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with output.with_suffix(output.suffix + ".sha256").open(
        "x", encoding="ascii"
    ) as stream:
        stream.write(digest + "  " + output.name + "\n")
    return {"bundle_sha256": digest, "revision": revision, "files": len(hashes)}


def seal_archive(source, revision, output):
    """Seal a host git-archive ZIP using a Python environment without Git."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("exact_committed_revision_required")
    output = local_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    singles = {
        "docs/AI_CONTRACTS.md",
        "docs/AI_VALIDATION.md",
        "docs/REQUIREMENTS.md",
        "scripts/validate_ai_contracts.py",
    }
    with ZipFile(source) as archive:
        if archive.comment.strip() != revision.encode("ascii"):
            raise ValueError("git_archive_revision_comment_mismatch")
    source_sha = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    with ZipFile(source) as archive, ZipFile(output, "x", ZIP_DEFLATED) as target:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if (
                name in hashes
                or "\\" in name
                or ".." in Path(name).parts
                or not (
                    name.startswith(
                        ("experiments/", "ai/", "evals/ai/", "docs/contracts/ai/")
                    )
                    or name in singles
                )
                or ".local" in Path(name).parts
                or ".env" in Path(name).parts
            ):
                raise ValueError("archive_inventory_not_allowed")
            content = archive.read(info)
            hashes[name] = hashlib.sha256(content).hexdigest()
            target.writestr(name, content)
        if not hashes:
            raise ValueError("empty_archive")
        target.writestr(
            "BUNDLE-MANIFEST.json",
            json.dumps(
                {
                    "mode": "portable_synthetic_source_no_inference",
                    "revision": revision,
                    "f2_reference_commit": F2_COMMIT,
                    "sha256": hashes,
                    "source_provenance": "git_archive_comment_matches_revision",
                    "source_archive_sha256": source_sha,
                },
                indent=2,
            ),
        )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with output.with_suffix(output.suffix + ".sha256").open(
        "x", encoding="ascii"
    ) as stream:
        stream.write(digest + "  " + output.name + "\n")
    return {"bundle_sha256": digest, "revision": revision, "files": len(hashes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "matrix", "bundle", "seal"])
    parser.add_argument("--output")
    parser.add_argument("--archive")
    parser.add_argument("--revision")
    parser.add_argument(
        "--sampler", choices=["matched", "recommended"], default="matched"
    )
    args = parser.parse_args()
    if args.command == "preflight":
        print(json.dumps(resources(), indent=2))
        return 0
    output = local_output(args.output)
    if args.command == "seal":
        print(json.dumps(seal_archive(args.archive, args.revision, output)))
    elif args.command == "bundle":
        print(json.dumps(bundle(output)))
    else:
        output.mkdir(parents=True, exist_ok=False)
        for name, cfg in matrix(args.sampler).items():
            exclusive_json(output / (name + ".json"), cfg)
        print(
            json.dumps(
                {
                    "mode": "configuration_only_no_inference",
                    "count": 4,
                    "sampler": args.sampler,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
