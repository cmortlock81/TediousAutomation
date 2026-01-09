"""Audit utilities for deterministic run metadata and manifests."""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class SourceManifestEntry:
    filename: str
    sha256: str
    size_bytes: int


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_source_manifest(files: Iterable[Path]) -> List[SourceManifestEntry]:
    entries = []
    for path in sorted(files, key=lambda item: item.name.lower()):
        entries.append(
            SourceManifestEntry(
                filename=path.name,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return entries


def run_id_from_manifest(entries: Iterable[SourceManifestEntry]) -> str:
    hasher = hashlib.sha256()
    for entry in entries:
        hasher.update(entry.sha256.encode("utf-8"))
    return hasher.hexdigest()


def git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def write_run_metadata(
    path: Path,
    run_id: str,
    git_commit: str,
    source_count: int,
    output_count: int,
) -> None:
    payload = {
        "run_id": run_id,
        "git_commit": git_commit,
        "source_count": source_count,
        "output_count": output_count,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def warn(message: str) -> None:
    logging.warning(message)
