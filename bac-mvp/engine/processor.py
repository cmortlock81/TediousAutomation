"""
SOURCE: The Boring Automation Company MVP
NOTE: Deterministic, audit‑safe processing only.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd
import pdfplumber

from .audit import build_source_manifest, git_commit_hash, run_id_from_manifest, write_run_metadata
from .config import SupplierConfig, VatRules, WorksTypeRule
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
        works_types: Sequence[WorksTypeRule],
        vat_rules: VatRules,
        sage_map: Dict[str, str],
    ) -> None:
        self._suppliers = list(suppliers)
        self._classifier = WorksTypeClassifier(works_types)
        self._vat_rate = vat_rules.default_rate
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

        processed_csv = output_folder / "processed_invoices.csv"
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
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"

        supplier_match = match_supplier(text, self._suppliers)
        if not supplier_match:
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
        inv_num = self._extract_value(config.inv_no, text)
        date = self._extract_value(config.date, text)
        po = self._extract_value(config.po, text)
        ref = self._extract_value(config.ref, text)

        doc_gross_total = self._extract_float(config.total_gross, text)
        is_credit = config.is_credit
        multiplier = -1 if is_credit else 1
        doc_gross_total = doc_gross_total * multiplier if is_credit else doc_gross_total

        rows = self._extract_line_items(config, text)
        validation = validate_totals(rows, doc_gross_total, self._vat_rate)
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
    def _extract_value(pattern: str, text: str) -> str:
        match = re.search(pattern, text)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_float(pattern: str, text: str) -> float:
        match = re.search(pattern, text)
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    @staticmethod
    def _extract_line_items(config: SupplierConfig, text: str) -> List[Dict[str, object]]:
        rows = []
        matches = re.findall(config.line_pattern, text)
        for match in matches:
            data_map = dict(zip(config.columns, match))
            qty = float(data_map["qty"])
            rate = float(data_map["rate"])
            rows.append(
                {
                    "desc": str(data_map["desc"]).replace("\n", " ").strip(),
                    "qty": qty,
                    "unit": data_map["unit"],
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
        df.drop_duplicates(subset=["SUPPLIER INVOICE NR", "INVOICE DESCRIPTION"], inplace=True)
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
