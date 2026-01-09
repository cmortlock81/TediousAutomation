Each processing run MUST output:
- processed_invoices.csv
- validation_report.csv
- run_metadata.json
- source_manifest.csv

Audit guarantees:
- Invoice hash (SHA256 of source)
- Run ID
- Script version (git commit)
- Deterministic output
- Explicit exception reporting
