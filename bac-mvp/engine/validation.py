"""Validation logic for invoice calculations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class ValidationResult:
    status: str
    doc_gross_total: float
    calc_gross_total: float
    variance: float


def validate_totals(
    rows: Iterable[dict],
    doc_gross_total: float,
    vat_rate: float,
    approval_tolerance: float,
) -> ValidationResult:
    calculated_net = sum(row["net"] for row in rows)
    calc_gross_total = round(calculated_net * (1 + vat_rate), 2)
    variance = abs(doc_gross_total - calc_gross_total)
    status = "OK" if variance <= approval_tolerance else "REVIEW"
    return ValidationResult(
        status=status,
        doc_gross_total=doc_gross_total,
        calc_gross_total=calc_gross_total,
        variance=round(variance, 2),
    )


def build_validation_report(
    invoice_number: str,
    supplier_name: str,
    validation: ValidationResult,
) -> List[dict]:
    return [
        {
            "invoice_number": invoice_number,
            "supplier": supplier_name,
            "status": validation.status,
            "doc_gross_total": validation.doc_gross_total,
            "calc_gross_total": validation.calc_gross_total,
            "variance": validation.variance,
        }
    ]
