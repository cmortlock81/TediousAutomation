"""
CLI entry point.

Accepts:
- Folder of PDFs or CSV
Outputs:
- Sage‑ready CSV
- Full audit pack
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import pandas as pd

from engine.config import load_suppliers, load_vat_rules, load_works_types
from engine.processor import InvoiceProcessor


def load_sage_map(path: Path) -> Dict[str, str]:
    sage_map: Dict[str, str] = {}
    if not path.exists():
        return sage_map
    sage_df = pd.read_csv(path)
    for _, row in sage_df.iterrows():
        if pd.notna(row.get("Name")) and pd.notna(row.get("A/C")):
            name_key = str(row["Name"]).strip().lower()
            sage_map[name_key] = str(row["A/C"]).strip()
    return sage_map


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="The Boring Automation Company – MVP")
    parser.add_argument("--input", type=Path, required=True, help="Folder containing PDFs")
    parser.add_argument("--output", type=Path, default=Path("output"), help="Output folder")
    parser.add_argument(
        "--suppliers",
        type=Path,
        default=Path("configs/suppliers.yaml"),
        help="Supplier configuration YAML",
    )
    parser.add_argument(
        "--works-types",
        type=Path,
        default=Path("configs/works_types.yaml"),
        help="Works types configuration YAML",
    )
    parser.add_argument(
        "--vat-rules",
        type=Path,
        default=Path("configs/vat_rules.yaml"),
        help="VAT rules configuration YAML",
    )
    parser.add_argument(
        "--sage-file",
        type=Path,
        default=Path("Sage Supplier Accounts.xlsx - Sheet1.csv"),
        help="Sage supplier mapping CSV",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    suppliers = load_suppliers(args.suppliers)
    works_types = load_works_types(args.works_types)
    vat_rules = load_vat_rules(args.vat_rules)
    sage_map = load_sage_map(args.sage_file)

    processor = InvoiceProcessor(
        suppliers=suppliers,
        works_types=works_types,
        vat_rules=vat_rules,
        sage_map=sage_map,
    )
    processor.process(args.input, args.output)


if __name__ == "__main__":
    main()
