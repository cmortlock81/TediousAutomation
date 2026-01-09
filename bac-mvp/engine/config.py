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
class SupplierMatchConfig:
    contains: str


@dataclass(frozen=True)
class SupplierDocumentConfig:
    invoice_number: str
    invoice_date: str
    purchase_order: str
    reference: str
    total_gross: str


@dataclass(frozen=True)
class SupplierLineConfig:
    regex: str
    columns: List[str]


@dataclass(frozen=True)
class SupplierVatConfig:
    credit_note: bool = False


@dataclass(frozen=True)
class SupplierConfig:
    key: str
    name: str
    match: SupplierMatchConfig
    document: SupplierDocumentConfig
    lines: SupplierLineConfig
    vat: SupplierVatConfig


@dataclass(frozen=True)
class WorksTypeRule:
    name: str
    patterns: List[str]


@dataclass(frozen=True)
class WorksTypesConfig:
    default: str
    rules: List[WorksTypeRule]


@dataclass(frozen=True)
class VatRules:
    default_rate: float
    approval_tolerance: float


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _require(payload: Dict[str, Any], key: str, context: str) -> Any:
    if key not in payload:
        raise ValueError(f"Missing required key '{key}' in {context} config.")
    return payload[key]


def _normalize_columns(columns: List[str]) -> List[str]:
    normalized = []
    for column in columns:
        if column == "desc":
            normalized.append("description")
        elif column == "qty":
            normalized.append("quantity")
        else:
            normalized.append(column)
    return normalized


def load_suppliers(path: Path) -> List[SupplierConfig]:
    payload = load_yaml(path)
    suppliers = payload.get("suppliers", [])
    if not isinstance(suppliers, list):
        raise ValueError("Suppliers config must contain a 'suppliers' list.")

    configs: List[SupplierConfig] = []
    for supplier in suppliers:
        if not isinstance(supplier, dict):
            raise ValueError("Each supplier entry must be a mapping.")
        supplier_info = _require(supplier, "supplier", "supplier")
        match_info = _require(supplier, "match", "supplier.match")
        document_info = _require(supplier, "document", "supplier.document")
        lines_info = _require(supplier, "lines", "supplier.lines")
        vat_info = supplier.get("vat", {})

        columns = _require(lines_info, "columns", "supplier.lines")
        normalized_columns = _normalize_columns(list(columns))
        required = {"description", "quantity", "unit", "rate"}
        missing_columns = required - set(normalized_columns)
        if missing_columns:
            raise ValueError(
                "Supplier lines columns missing required fields: "
                f"{', '.join(sorted(missing_columns))}."
            )

        configs.append(
            SupplierConfig(
                key=_require(supplier_info, "key", "supplier.supplier"),
                name=_require(supplier_info, "name", "supplier.supplier"),
                match=SupplierMatchConfig(contains=_require(match_info, "contains", "supplier.match")),
                document=SupplierDocumentConfig(
                    invoice_number=_require(document_info, "invoice_number", "supplier.document"),
                    invoice_date=_require(document_info, "invoice_date", "supplier.document"),
                    purchase_order=_require(document_info, "purchase_order", "supplier.document"),
                    reference=_require(document_info, "reference", "supplier.document"),
                    total_gross=_require(document_info, "total_gross", "supplier.document"),
                ),
                lines=SupplierLineConfig(
                    regex=_require(lines_info, "regex", "supplier.lines"),
                    columns=normalized_columns,
                ),
                vat=SupplierVatConfig(credit_note=bool(vat_info.get("credit_note", False))),
            )
        )
    return configs


def load_works_types(path: Path) -> WorksTypesConfig:
    payload = load_yaml(path)
    rules = payload.get("works_types", [])
    if not isinstance(rules, list):
        raise ValueError("Works types config must contain a 'works_types' list.")
    default = str(payload.get("default", "OTHER"))
    return WorksTypesConfig(
        default=default,
        rules=[WorksTypeRule(**rule) for rule in rules],
    )


def load_vat_rules(path: Path) -> VatRules:
    payload = load_yaml(path)
    vat = payload.get("vat", {})
    default_rate = float(vat.get("default_rate", 0.0))
    approval_tolerance = float(vat.get("approval_tolerance", 0.5))
    return VatRules(default_rate=default_rate, approval_tolerance=approval_tolerance)
