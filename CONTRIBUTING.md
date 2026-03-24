# Contributing

## Project structure

```
src/agents/          One file per agent — add new agents here
src/utils/           Shared utilities (date normalization, validation)
cli/                 Terminal interface
api/                 FastAPI REST server
ui/                  Streamlit web interface
tests/               pytest test suite
examples/            Sample transcripts for manual testing
```

## Adding a new agent

1. Create `src/agents/your_agent.py` — follow the pattern of existing agents
2. Import and call it in `src/pipeline.py` in the correct sequence
3. Add tests in `tests/test_extended.py`

## Running locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# CLI
python -m cli.run examples/q3_product_hr_sync.txt --date 2025-07-14

# API
uvicorn api.server:app --reload

# Web UI
streamlit run ui/app.py

# Tests (no API key needed)
pytest tests/ -v
```

## Pull request checklist

- [ ] `pytest tests/` passes with no failures
- [ ] `ruff check src/ cli/ api/ ui/ tests/` passes
- [ ] New agents have matching tests
- [ ] `.env` is not committed (check `.gitignore`)
- [ ] README updated if behaviour changes
