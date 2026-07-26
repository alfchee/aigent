Run only the tests for a specific module. Usage: replace `<module>` with the
test file name without the `test_` prefix (e.g. `provider_config` →
runs `test_provider_config_endpoint.py`).

```bash
cd backend && PYTHONPATH=. python -m pytest tests/test_$ARGUMENTS.py -v
```
