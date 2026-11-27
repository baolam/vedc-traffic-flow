"""Atomic artifacts and semantic identities; failed attempts are never overwritten."""

import hashlib
import json
import os
import shutil
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot_source(root):
    files = sorted(
        p
        for folder in ("src/benchmark", "src/simulation", "src/control", "src/rl", "contracts", "configs/benchmarks")
        for p in Path(folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and (p.suffix in (".py", ".json", ".yaml", ".yml"))
    )
    manifest = {str(path): file_hash(path) for path in files}
    target = Path(root) / "source" / digest(manifest)
    for path in files:
        destination = target / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(path, destination)
        if file_hash(destination) != manifest[str(path)]:
            raise ValueError(f"Source snapshot mismatch: {path}")
    write_json(target / "manifest.json", manifest)
    return str(target)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def execute_case(root, identity, execute):
    directory = Path(root) / digest(identity)
    complete = directory / "complete.json"
    if (directory / "invalid.json").exists():
        raise ValueError("Scientifically invalid case retained; use new inputs or a new campaign")
    if complete.exists():
        result = json.loads(complete.read_text())
        if result["identity"] != identity:
            raise ValueError("Case identity mismatch")
        if not result["metrics"].get("valid"):
            raise ValueError("Invalid completed case cannot be reused")
        return result["metrics"]
    directory.mkdir(parents=True, exist_ok=True)
    attempts = list(directory.glob("attempt-*"))
    attempt = directory / f"attempt-{len(attempts) + 1:04d}"
    attempt.mkdir()
    write_json(attempt / "identity.json", identity)
    try:
        metrics = execute(attempt / "run")
        if not metrics.get("valid"):
            write_json(directory / "invalid.json", metrics)
            raise ValueError("Case failed scientific validity")
        write_json(complete, dict(identity=identity, metrics=metrics))
        return metrics
    except BaseException as error:
        if getattr(error, "scientifically_invalid", False):
            write_json(directory / "invalid.json", dict(valid=False, reason=str(error)))
        write_json(attempt / "failure.json", dict(valid=False, reason=str(error)))
        raise
