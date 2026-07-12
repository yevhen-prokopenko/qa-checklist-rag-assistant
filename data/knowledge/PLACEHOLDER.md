# Knowledge base (past verified checklists)

Drop 5–10 JSON files here — each = one past QA task. Format:

```json
{
  "source_key": "QA-1201",
  "domain": "wms-transfer",
  "task": "Short task / TЗ description",
  "checklist": ["check 1", "check 2", "check 3"],
  "approved": true
}
```

TODO(Eugene): we generate these together once you give the domain context
(WMS / transfers / web-checkout etc.). Then run `python ingest.py`.
