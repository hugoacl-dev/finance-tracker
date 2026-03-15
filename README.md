# Finance Tracker

Personal finance management application built with **Streamlit**, **Supabase**, and **Google Gemini AI**.

Track expenses, analyze spending patterns, and get AI-powered financial insights — all from a modern web dashboard with optional mobile integration via a FastAPI backend.

## Features

- **Cycle Analysis (Raio-X)** — Real-time spending breakdown with financial health score, budget progress bars, and anomaly detection
- **Historical Evolution** — Multi-month trend analysis with forecasting (EMA) and seasonality detection
- **AI Insights** — Gemini-powered financial consultant chatbot with customizable prompts
- **OCR Import** — Extract transactions from credit card statement images using Gemini Vision
- **Multi-profile** — Support for multiple card holders (Principal / Dependente) with card-based routing
- **Mobile Import** — FastAPI backend (`api-fatura/`) for importing statement photos directly from iPhone Shortcuts
- **Financial Independence Calculator** — FIRE projections based on current savings rate

## Architecture

```
app.py                      # Streamlit entrypoint
core/
  config.py                 # Default configuration
  models.py                 # Data models
  utils.py                  # Shared utilities (mes_sort_key, etc.)
services/
  data_service.py           # Abstract DataService interface
  supabase_adapter.py       # Supabase implementation
  data_engine.py            # Business logic (scoring, dedup, filtering)
  ocr_gemini.py             # Gemini OCR + AI classification
  forecasting.py            # EMA forecasting, trends, seasonality
views/
  tab_raiox.py              # Cycle analysis tab
  tab_historico.py          # Historical evolution tab
  tab_importacao.py         # AI insights / chatbot tab
  tab_settings.py           # Settings, imports, manual entry
  onboarding.py             # First-run onboarding flow
  styles.py                 # CSS styles
api-fatura/
  main.py                   # FastAPI backend (deployed on Render)
tests/
  conftest.py               # Pytest fixtures
  test_data_engine.py       # Core engine tests
  test_new_features.py      # Score, anomaly, forecasting tests
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit, Plotly |
| Backend API | FastAPI (Uvicorn) |
| Database | Supabase (PostgreSQL) |
| AI/OCR | Google Gemini (genai SDK) |
| Hosting | Streamlit Cloud + Render |

## Setup

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project
- A [Google AI Studio](https://aistudio.google.com) API key

### 1. Clone and install dependencies

```bash
git clone https://github.com/<your-user>/finance-tracker.git
cd finance-tracker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure secrets

Copy the example files and fill in your credentials:

```bash
cp .env.example .env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

### 3. Set up Supabase

Create the following tables in your Supabase project:

- **profiles** — User profiles with configuration (Receita_Base, Meta_Aporte, Teto_Gastos, etc.)
- **mensal_data** — Monthly fixed expenses
- **transacoes_data** — Variable transactions per cycle

Run the migration scripts in `scripts/` for additional tables (goals, category budgets).

### 4. Run locally

```bash
streamlit run app.py
```

### API (optional)

The `api-fatura/` directory contains an independent FastAPI service for importing statement images from mobile devices:

```bash
cd api-fatura
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT
