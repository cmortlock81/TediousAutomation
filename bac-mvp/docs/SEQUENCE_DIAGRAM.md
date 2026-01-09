```mermaid
sequenceDiagram
  Smartsheet->>Processor: Export CSV
  Processor->>Validation: Run checks
  Validation->>Audit: Record results
  Processor->>CSV: Generate Sage import
```
