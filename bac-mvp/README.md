# The Boring Automation Company – MVP

Audit‑compliant automation that converts Smartsheet data and supplier PDFs
into Sage 50–ready CSV imports.

Principles:
- Deterministic processing
- Full audit traceability
- No auto‑posting to Sage
- Human approval required

Target users:
Construction businesses using Smartsheet + Sage 50.

## Running the invoice parser
1. Place supplier PDFs into a folder (e.g. `invoices/`).
2. Ensure each supplier has a YAML definition under `configs/suppliers/`, and VAT/works types are configured in `configs/`.
3. Run the CLI:

```bash
python cli.py --input invoices --output output
```

The SmartSheet-compatible CSV is written to `output/SmartSheet_Import_v3.2.csv`. VAT defaults to 20% unless overridden in `configs/vat_rules.yaml`.
