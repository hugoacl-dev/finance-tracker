# Finance Tracker — Agent Guide

> Personal finance management application built with Streamlit, Supabase, and Google Gemini AI.
> This guide is intended for AI coding agents working on this codebase.

---

## Project Overview

Finance Tracker is a Brazilian Portuguese personal finance dashboard that helps users:
- Track expenses across monthly cycles (credit card based)
- Analyze spending patterns with AI-powered insights
- Import transactions from credit card statement images (OCR)
- Calculate financial health scores and FIRE (Financial Independence) projections
- Manage multiple profiles (Principal / Dependente)

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit 1.55.0, Plotly |
| Backend API | FastAPI (Uvicorn) — optional mobile import service |
| Database | Supabase (PostgreSQL) |
| AI/OCR | Google Gemini (genai SDK) |
| Data Processing | Pandas, NumPy |
| Hosting | Streamlit Cloud + Render |

---

## Project Structure

```
app.py                      # Streamlit entrypoint

# Core layer — configuration, models, utilities
core/
  __init__.py
  config.py                 # Default configuration values (DEFAULTS dict)
  models.py                 # Pydantic models (Transacao)
  utils.py                  # mes_sort_key() for month sorting

# Services layer — business logic and data access
services/
  __init__.py               # get_data_service() factory (singleton)
  data_service.py           # Abstract DataService interface (ABC)
  supabase_adapter.py       # Supabase implementation of DataService
  data_engine.py            # Business logic: scoring, dedup, filtering, FIRE calc
  ocr_gemini.py             # Gemini Vision OCR + text classification
  forecasting.py            # EMA forecasting, trends, seasonality analysis

# Views layer — UI components
views/
  __init__.py
  styles.py                 # CSS styles with dark/light theme support
  onboarding.py             # 4-step first-run wizard
  tab_raiox.py              # Cycle analysis tab (main dashboard)
  tab_historico.py          # Historical evolution tab
  tab_importacao.py         # AI insights / chatbot tab
  tab_settings.py           # Settings, imports, manual entry

# Mobile API — independent FastAPI service
api-fatura/
  main.py                   # FastAPI backend for iPhone Shortcuts integration

# Tests
tests/
  conftest.py               # pytest fixtures
  test_data_engine.py       # Unit tests for core engine functions
  test_new_features.py      # Tests for score, anomaly, forecasting

# Configuration
.env.example               # Environment variables template
.streamlit/
  secrets.toml.example     # Streamlit secrets template
scripts/
  migration_goals_budgets.sql  # SQL for goals and category_budgets tables
```

---

## Database Schema (Supabase)

### Tables

**profiles**
- `id`: UUID PK
- `name`: STRING ("Principal", "Dependente")
- `receita_base`, `meta_aporte`, `teto_gastos`: NUMERIC
- `dia_fechamento`: INT (day of month)
- `gemini_model`, `gemini_vision_model`: STRING
- `regras_ia`: TEXT (custom classification rules)
- `cartoes_aceitos`, `cartoes_excluidos`: ARRAY/JSON (card filtering)
- `onboarding_done`: BOOLEAN
- `ultima_importacao`: TIMESTAMPTZ

**gastos_fixos** (monthly fixed expenses)
- `id`: UUID PK
- `profile_id`: UUID FK → profiles
- `mes`: STRING (format "MM/YY" or "Mês YY")
- `descricao_fatura`: TEXT
- `valor`: NUMERIC
- `tipo`: STRING ("Nao_Cartao", "Cartao", "Extra")
- `status_conciliacao`: STRING ("⏳ Pendente", "✅ Confirmado")

**transacoes** (variable transactions)
- `id`: UUID PK
- `profile_id`: UUID FK → profiles
- `mes`: STRING
- `descricao`: TEXT
- `valor`: NUMERIC
- `cartao`: STRING (last 4 digits)
- `titular`: STRING
- `categoria`: STRING (one of: Alimentação, Supermercado, Transporte, Saúde, Assinatura, Lazer, Pet, Compras, Combustível, Casa, Outros)

**goals** (long-term financial goals)
- `id`: UUID PK
- `profile_id`: UUID FK
- `titulo`: TEXT
- `valor_alvo`: NUMERIC
- `prazo_meses`: INT

**category_budgets** (spending limits per category)
- `id`: UUID PK
- `profile_id`: UUID FK
- `categoria`: TEXT
- `limite`: NUMERIC
- Unique: (profile_id, categoria)

---

## Configuration Files

### Environment Variables (.env)
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
GEMINI_API_KEY=your-gemini-api-key
API_TOKEN=your-api-token  # For api-fatura authentication
```

### Streamlit Secrets (.streamlit/secrets.toml)
```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key"
GEMINI_API_KEY = "your-gemini-api-key"
```

---

## Build and Run Commands

### Local Development

```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Streamlit app
streamlit run app.py

# Run FastAPI (optional, in separate terminal)
cd api-fatura
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_data_engine.py -v

# Run with coverage
pytest tests/ --cov=services --cov=core -v
```

---

## Code Style Guidelines

### Python Style
- **Language**: Portuguese (Brazil) for business logic, English for technical terms
- **Docstrings**: Portuguese with type hints
- **Comments**: Use `# ═══════════════════════════════════════` for section headers
- **String quotes**: Double quotes for UI strings, single quotes acceptable elsewhere
- **Line length**: ~100 characters (no strict limit)

### Naming Conventions
- Functions/variables: `snake_case` (e.g., `calcular_score_financeiro`)
- Classes: `PascalCase` (e.g., `SupabaseAdapter`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULTS`, `PROMPT_OCR`)
- Database columns: `snake_case` (e.g., `receita_base`)
- Session state keys: `snake_case` with Portuguese names (e.g., `perfil_ativo`, `cfg`)

### Key Patterns

**DataService Pattern** (Repository/Adapter):
```python
# services/data_service.py defines abstract interface
# services/supabase_adapter.py implements it
# Use factory in services/__init__.py:
from services import get_data_service
data_service = get_data_service()  # Singleton
```

**Session State Access**:
```python
cfg = st.session_state.get("cfg", {})
transacoes_data = st.session_state.get("transacoes_data", {})
perfil_ativo = st.session_state.get("perfil_ativo", "Principal")
```

**Month Sorting**:
```python
from core.utils import mes_sort_key
all_meses = sorted(list(transacoes_data.keys()), key=mes_sort_key)
```

---

## Testing Strategy

### Test Structure
- **Unit tests**: `tests/test_data_engine.py` for pure functions
- **Feature tests**: `tests/test_new_features.py` for score, forecasting
- **Fixtures**: `tests/conftest.py` provides sample DataFrames

### Testing Guidelines
1. Mock external dependencies (Supabase, Gemini API)
2. Use `pytest.approx()` for float comparisons
3. Test edge cases (empty DataFrames, zero values, None)
4. Portuguese test names are acceptable and used

### Running Tests
```bash
pytest tests/ -v
```

---

## Security Considerations

### API Authentication
- `api-fatura/main.py` requires `Authorization: Bearer <API_TOKEN>` header
- Token is set via environment variable `API_TOKEN`

### Database Security
- Supabase uses Row Level Security (RLS) — see migration SQL for policies
- Anonymous key has limited permissions
- Service role key should never be exposed to frontend

### Secrets Management
- Never commit `.env` or `.streamlit/secrets.toml`
- Both are listed in `.gitignore`
- Use Streamlit secrets API: `st.secrets["GEMINI_API_KEY"]`

---

## Key Business Logic

### Month Cycle Format
- Primary format: `"MM/YY"` (e.g., "03/25" for March 2025)
- Also supported: `"Mês YY"` (e.g., "Março 25")
- Use `mes_sort_key()` from `core.utils` for chronological sorting

### Financial Health Score (0-100)
Calculated in `calcular_score_financeiro()` with 5 pillars:
1. Savings Rate (30 pts)
2. Aderência ao Teto (25 pts)
3. Meta de Aporte (20 pts)
4. Consistência (15 pts)
5. Organização (10 pts)

### Duplicate Detection (Dedup)
Three-pass matching in `dedup_transacoes()`:
1. Exact match (description 100%, value exact)
2. Similar description (≥80%), value exact
3. Very similar description (≥90%), value ±0.50

### FIRE Calculator
Rule of 4%: `patrimonio_necessario = custo_mensal × 12 / 0.04`

---

## Common Development Tasks

### Adding a New View Tab
1. Create `views/tab_newname.py` with `render_page()` function
2. Import in `app.py`
3. Add to `st.tabs()` call in the main flow

### Adding a New Data Service Method
1. Add abstract method to `services/data_service.py`
2. Implement in `services/supabase_adapter.py`
3. Add corresponding table/columns in Supabase
4. Write tests in `tests/`

### Modifying the Database Schema
1. Write SQL migration in `scripts/`
2. Run in Supabase SQL Editor
3. Update `SupabaseAdapter` methods
4. Update Pydantic models if needed

---

## Deployment

### Streamlit Cloud
- Entrypoint: `app.py`
- Python version: 3.11+
- Secrets configured in Streamlit Cloud dashboard

### API (Render)
- Directory: `api-fatura/`
- Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables from `.env`

---

## Useful Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Supabase Python Client](https://supabase.com/docs/reference/python/)
- [Google Gemini API](https://ai.google.dev/)
- [Plotly Python](https://plotly.com/python/)
