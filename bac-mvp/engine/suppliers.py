"""Supplier parsing helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .config import SupplierConfig


@dataclass(frozen=True)
class SupplierMatch:
    config: SupplierConfig


def match_supplier(text: str, suppliers: Iterable[SupplierConfig]) -> Optional[SupplierMatch]:
    for supplier in suppliers:
        if supplier.check in text:
            return SupplierMatch(config=supplier)
    return None
