"""
SOURCE: The Boring Automation Company MVP
NOTE: Deterministic, audit‑safe processing only.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd
import pdfplumber

from .audit import build_source_manifest, git_commit_hash, run_id_from_manifest, warn, write_run_metadata
from .config import SupplierConfig, VatRules, WorksTypesConfig
from .suppliers import match_supplier
from .validation import build_validation_report, validate_totals
from .works_types import WorksTypeClassifier


@dataclass(frozen=True)
class ProcessedLine:
    data: Dict[str, object]


class InvoiceProcessor:
    def __init__(
        self,
        suppliers: Sequence[SupplierConfig],
        works_types: WorksTypesConfig,
        vat_rules: VatRules,
        sage_map: Dict[str, str],
    ) -> None:
        self._suppliers = list(suppliers)
        self._classifier = WorksTypeClassifier(works_types)
        self._vat_rate = vat_rules.default_rate
        self._approval_tolerance = vat_rules.approval_tolerance
        self._sage_map = sage_map

    def process(self, input_folder: Path, output_folder: Path) -> None:
        pdf_files = sorted(input_folder.glob("*.pdf"), key=lambda item: item.name.lower())
        output_folder.mkdir(parents=True, exist_ok=True)

        manifest = build_source_manifest(pdf_files)
        run_id = run_id_from_manifest(manifest)
        git_commit = git_commit_hash()

        processed_rows: List[Dict[str, object]] = []
        validation_rows: List[Dict[str, object]] = []

        for pdf_path in pdf_files:
            extraction = self._extract_pdf_data(pdf_path)
            processed_rows.extend(extraction.processed_rows)
            validation_rows.extend(extraction.validation_rows)

        processed_csv = output_folder / "SmartSheet_Import_v3.2.csv"
        validation_csv = output_folder / "validation_report.csv"
        source_manifest_csv = output_folder / "source_manifest.csv"
        run_metadata_json = output_folder / "run_metadata.json"

        self._write_processed_csv(processed_csv, processed_rows)
        self._write_validation_csv(validation_csv, validation_rows)
        self._write_source_manifest(source_manifest_csv, manifest)
        write_run_metadata(
            run_metadata_json,
            run_id=run_id,
            git_commit=git_commit,
            source_count=len(manifest),
            output_count=len(processed_rows),
        )

    def _sage_code(self, supplier_name: str) -> str:
        name_clean = supplier_name.lower().strip()
        if name_clean in self._sage_map:
            return self._sage_map[name_clean]
        for sage_name, code in self._sage_map.items():
            if "hilti" in name_clean and "hilti" in sage_name:
                return code
            if "sig" in name_clean and "sig" in sage_name:
                return code
            if "arnold" in name_clean and "arnold" in sage_name:
                return code
        return ""

    def _extract_pdf_data(self, filepath: Path) -> "ExtractionResult":
        text = self._extract_text(filepath)

        supplier_match = match_supplier(text, self._suppliers)
        if not supplier_match:
            warn(f"Skipped {filepath.name}: Unknown supplier")
            return ExtractionResult(processed_rows=[], validation_rows=[
                {
                    "invoice_number": "",
                    "supplier": "Unknown",
                    "status": "SKIPPED_UNKNOWN_SUPPLIER",
                    "doc_gross_total": 0.0,
                    "calc_gross_total": 0.0,
                    "variance": 0.0,
                }
            ])

        config = supplier_match.config
        header, header_warnings = self._extract_header(config, text)
        for warning in header_warnings:
            warn(f"{filepath.name}: {warning}")

        is_credit = config.vat.credit_note
        multiplier = -1 if is_credit else 1

        rows = self._extract_line_items(config, text)
        if not rows:
            warn(f"WARNING: No line items found in {filepath.name}")

        validation = validate_totals(
            rows,
            header["doc_gross_total"],
            self._vat_rate,
            self._approval_tolerance,
        )
        inv_num = header["invoice_number"]
        date = header["invoice_date"]
        po = header["purchase_order"]
        ref = header["reference"]
        validation_rows = build_validation_report(inv_num, config.name, validation)

        ipl_ref, job_code = self._parse_filename(filepath.name)
        sage_code = self._sage_code(config.name)

        processed_rows = []
        for row in rows:
            final_net = row["net"] * multiplier
            final_vat = final_net * self._vat_rate
            final_gross = final_net + final_vat
            processed_rows.append(
                {
                    "IPL REF": ipl_ref,
                    "SUPPLIER": config.name,
                    "Sage": sage_code,
                    "MAIL DATE": "",
                    "INVOICE DATE": date,
                    "SUPPLIER REF": ref,
                    "INVOICE DESCRIPTION": row["desc"],
                    "WORKS TYPE": self._classifier.classify(row["desc"]),
                    "QUANTITY": row["qty"],
                    "UNIT": row["unit"],
                    "RATE": row["rate"],
                    "NET": round(final_net, 2),
                    "VAT": round(final_vat, 2),
                    "GROSS": round(final_gross, 2),
                    "SUPPLIER INVOICE NR": inv_num,
                    "Invoice approved": validation.status,
                    "PO Number": po,
                    "Job Code": job_code,
                    "Job Name": "",
                }
            )

        return ExtractionResult(processed_rows=processed_rows, validation_rows=validation_rows)

    @staticmethod
    def _extract_text(filepath: Path) -> str:
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    @staticmethod
    def _safe_group(pattern: str, text: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_header(
        self,
        config: SupplierConfig,
        text: str,
    ) -> Tuple[Dict[str, object], List[str]]:
        warnings: List[str] = []
        invoice_number = self._safe_group(config.document.invoice_number, text)
        invoice_date = self._safe_group(config.document.invoice_date, text)
        purchase_order = self._safe_group(config.document.purchase_order, text)
        reference = self._safe_group(config.document.reference, text)
        doc_gross_raw = self._safe_group(config.document.total_gross, text)
        doc_gross_total = 0.0
        if doc_gross_raw:
            try:
                doc_gross_total = float(doc_gross_raw)
            except ValueError:
                warnings.append("Document total gross could not be parsed")

        missing = []
        if not invoice_number:
            missing.append("invoice number")
        if not invoice_date:
            missing.append("invoice date")
        if not purchase_order:
            missing.append("purchase order")
        if not reference:
            missing.append("reference")
        if missing:
            warnings.append(f"Missing header fields: {', '.join(missing)}")
        if not doc_gross_raw:
            warnings.append("Document total gross not found")

        header = {
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "purchase_order": purchase_order,
            "reference": reference,
            "doc_gross_total": doc_gross_total,
        }
        return header, warnings

    @staticmethod
    def _extract_line_items(config: SupplierConfig, text: str) -> List[Dict[str, object]]:
        rows = []
        matches = re.findall(config.lines.regex, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            data_map = dict(zip(config.lines.columns, match))
            try:
                qty = float(data_map["quantity"])
            except (ValueError, TypeError, KeyError):
                qty = 0.0
            try:
                rate = float(data_map["rate"])
            except (ValueError, TypeError, KeyError):
                rate = 0.0
            rows.append(
                {
                    "desc": str(data_map.get("description", "")).replace("\n", " ").strip(),
                    "qty": qty,
                    "unit": data_map.get("unit", ""),
                    "rate": rate,
                    "net": round(qty * rate, 2),
                }
            )
        return rows

    @staticmethod
    def _parse_filename(filename: str) -> tuple[str, str]:
        base = os.path.splitext(os.path.basename(filename))[0]
        base = re.sub(r"\(\d+\)", "", base).strip()
        parts = base.split("-")
        return (parts[0], parts[1]) if len(parts) >= 2 else (base, "")

    @staticmethod
    def _write_processed_csv(path: Path, rows: Iterable[Dict[str, object]]) -> None:
        columns = [
            "IPL REF",
            "SUPPLIER",
            "Sage",
            "MAIL DATE",
            "INVOICE DATE",
            "SUPPLIER REF",
            "INVOICE DESCRIPTION",
            "WORKS TYPE",
            "QUANTITY",
            "UNIT",
            "RATE",
            "NET",
            "VAT",
            "GROSS",
            "SUPPLIER INVOICE NR",
            "Invoice approved",
            "PO Number",
            "Job Code",
            "Job Name",
        ]
        df = pd.DataFrame(list(rows), columns=columns)
        df.drop_duplicates(subset=["SUPPLIER INVOICE NR", "INVOICE DESCRIPTION", "NET"], inplace=True)
        df.to_csv(path, index=False)

    @staticmethod
    def _write_validation_csv(path: Path, rows: Iterable[Dict[str, object]]) -> None:
        df = pd.DataFrame(list(rows))
        df.to_csv(path, index=False)

    @staticmethod
    def _write_source_manifest(path: Path, manifest_entries: Iterable) -> None:
        df = pd.DataFrame(
            [
                {"filename": entry.filename, "sha256": entry.sha256, "size_bytes": entry.size_bytes}
                for entry in manifest_entries
            ]
        )
        df.to_csv(path, index=False)


@dataclass(frozen=True)
class ExtractionResult:
    processed_rows: List[Dict[str, object]]
    validation_rows: List[Dict[str, object]]
