## Objective
Provide a safe control layer between Smartsheet/PDF inputs and Sage 50.

## Core Workflow
Smartsheet / PDFs → Validation → Approval → CSV Export → Sage Import

## Non‑Goals
- No direct Sage API posting
- No bi‑directional sync
- No AI decision‑making

## Success Criteria
- Zero silent data changes
- Full audit trail per run
- CSV imports succeed first time
