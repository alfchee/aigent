# Linting

## Instalación

Python:

```
pip install -r backend/requirements.txt
```

Frontend:

```
cd frontend
npm install
```

Root (husky):

```
cd ..
npm install
```

## Uso

Python:

```
flake8 backend
```

Frontend:

```
cd frontend
npm run lint
```

Configuración frontend:

- eslint: frontend/.eslintrc.cjs
- prettier: frontend/.prettierrc

Todo el repositorio:

```
npm run lint
```

## Hooks

Los hooks de git se activan en cada commit y ejecutan los linters de Python y Vue.
