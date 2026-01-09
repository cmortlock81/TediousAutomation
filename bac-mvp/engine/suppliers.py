"""Supplier parsing helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .config import SupplierConfig


@dataclass(frozen=True)
class SupplierMatch:
    config: SupplierConfig


def match_supplier(text: str, suppliers: Iterable[SupplierConfig]) -> Optional[SupplierMatch]:
    lowered_text = text.lower()
    for supplier in suppliers:
        if supplier.match.contains.lower() in lowered_text:
            return SupplierMatch(config=supplier)
    return None
