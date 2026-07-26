Run the full backend test suite (excludes network tests).

```bash
cd backend && PYTHONPATH=. python -m pytest tests -v -m "not network"
```
