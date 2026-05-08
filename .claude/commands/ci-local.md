Run the complete CI pipeline locally (mirrors `.github/workflows/ci.yml`).

```bash
# Backend
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. python -m pytest tests -v -m "not network"
cd backend && python -m compileall app -q
cd ..

# Frontend
cd frontend
npm install
npm run lint
npm test
npm run build
```
