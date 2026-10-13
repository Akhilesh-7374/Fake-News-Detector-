# Production Deployment & Operations Guide

## 1. Local Environment Run

```bash
# 1. Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS / Linux

# 2. Run the Streamlit Enterprise Dashboard
streamlit run src/company_dashboard.py

# 3. Or run the FastAPI REST API
uvicorn src.realtime_api:app --host 0.0.0.0 --port 8000 --reload

# 4. Or run the background ingestion worker
python src/cli.py run-worker --interval 60 --provider composite
```

---

## 2. Docker Deployment

Build and run using Docker Compose:

```bash
docker-compose up --build
```

This starts:
1. `web-dashboard`: Streamlit dashboard on port `8501`.
2. `api-server`: FastAPI REST API on port `8000`.
3. `ingestion-worker`: Background news monitoring service.
