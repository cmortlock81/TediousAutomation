"""
Configuration loading utilities.
Deterministic, audit-safe behavior only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass(frozen=True)
class SupplierConfig:
    key: str
    check: str
    name: str
    inv_no: str
    date: str
    po: str
    ref: str
    total_gross: str
    line_pattern: str
    columns: List[str]
    is_credit: bool = False


@dataclass(frozen=True)
class WorksTypeRule:
    name: str
    patterns: List[str]


@dataclass(frozen=True)
class VatRules:
    default_rate: float


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_suppliers(path: Path) -> List[SupplierConfig]:
    payload = load_yaml(path)
    suppliers = payload.get("suppliers", [])
    return [SupplierConfig(**supplier) for supplier in suppliers]


def load_works_types(path: Path) -> List[WorksTypeRule]:
    payload = load_yaml(path)
    rules = payload.get("works_types", [])
    return [WorksTypeRule(**rule) for rule in rules]


def load_vat_rules(path: Path) -> VatRules:
    payload = load_yaml(path)
    vat = payload.get("vat", {})
    return VatRules(default_rate=float(vat.get("default_rate", 0.0)))
