```mermaid
erDiagram
  COST_LINE ||--o{ ISSUE : has
  EXPORT_BATCH ||--o{ COST_LINE : contains
  EXPORT_BATCH ||--o{ AUDIT_EVENT : records
```
