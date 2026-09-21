# CAT Prep AI Frontend

This Vite React frontend connects to the FastAPI backend for the student dashboard, adaptive practice, results, and performance views.

## Run locally

From this directory:

```powershell
npm install
npm run dev
```

The frontend runs at `http://127.0.0.1:5173`. Start the backend separately from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Set `VITE_API_URL` when the API is hosted somewhere other than `http://127.0.0.1:8000`.

## Checks

```powershell
npm test
npm run build
```
