# WindDesk — Wind Forecast Decision Dashboard

A React + FastAPI dashboard for evaluating the wind-generation forecast information available when a UK electricity buyer makes a purchase decision. The analysis uses only Elexon BMRS `FUELHH` (filtered to `fuelType=WIND`) actuals and `WINDFOR` forecast records, as requested in the challenge.

## Methodology

- The dashboard defaults to a **24-hour decision lead**, reflecting the day-ahead purchase context. The lead time is adjustable from 6 to 48 hours for sensitivity analysis.
- The analysis window is **purchase decision times in January 2026**, not simply delivery intervals occurring in January. With a 24-hour lead, delivery intervals can extend into early February.
- For each delivery interval, the API selects the forecast with the latest `publishTime` that is at or before `startTime - lead_hours`. This prevents forecasts published after the assumed decision from leaking into the evaluation.
- Intervals without both an actual generation value and an eligible forecast are excluded.
- Error is defined as `forecast - actual`. MAE and RMSE are in MW. Positive bias means over-forecasting; negative bias means under-forecasting.
- This is a prototype assumption: the exact internal decision timestamp was not specified, so the lead time is exposed in the UI and defaults to 24 hours.

## Project structure

```text
.
├── backend/
│   ├── Dockerfile          # FastAPI container
│   ├── main.py             # Elexon data access, matching, metrics, API routes
│   ├── requirements.txt    # Python dependencies
│   └── test_main.py        # Unit tests for matching and metrics
├── frontend/
│   ├── index.html          # Vite HTML entry point
│   ├── package.json        # React, Vite, Recharts and Lucide dependencies
│   └── src/
│       ├── main.jsx        # Dashboard UI, controls, chart and data table
│       └── styles.css      # Responsive dashboard styles
├── docker-compose.yml      # Runs frontend and backend together
├── render.yaml             # Optional Render backend deployment blueprint
└── README.md

The frontend directory also contains `vercel.json` for Vercel routing.
```

## Run with Docker

Install Docker Desktop and ensure it is running. From the project root:

```bash
docker compose up --build
```

- Frontend: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/api/health>
- Dashboard JSON: <http://localhost:8000/api/dashboard>

Stop the containers with `Ctrl+C`, then run `docker compose down`.

## Run locally without Docker

Backend (Python 3.11+ recommended), from `backend/`:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend, from `frontend/` in a second terminal:

```bash
npm install
npm run dev
```

## Tests

From `backend/` after installing the dependencies:

```bash
pip install pytest
pytest -q
```

## Data source and AI disclosure

- Elexon BMRS API: <https://data.elexon.co.uk/bmrs/api/v1>
- Actuals: `GET /datasets/FUELHH/stream`, filtered to `fuelType=WIND`
- Forecasts: `GET /datasets/WINDFOR/stream`
- API documentation: <https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream> and <https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream>

AI tools (ChatGPT) were used to assist with planning, implementation, and review. The API response and live-data assumptions should be validated against Elexon's live service before final submission.

## Deployment and submission checklist

- [ ] Deploy frontend to Vercel (project root: `frontend/`) and backend to Render using `render.yaml`; configure frontend `VITE_API_URL` and backend `CORS_ORIGINS` for the deployed domains.
- [ ] Add the live application URL here.
- [ ] Publish this source in a public GitHub repository with an anonymous/random repository name, as requested.
- [ ] Record an unlisted YouTube video no longer than 10 minutes: customer-facing overview (max 5 minutes) followed by technical review (max 5 minutes).
- [ ] Open every submitted URL in an incognito/private browser window before submitting the form.
