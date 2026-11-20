# Development notes

[中文版](development.zh-CN.md)

Things I keep needing when working on the code.

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # or: pip install -e ".[dev]"
python scripts/fetch_models.py --skip-ocr  # tokenizer data; leave out --skip-ocr if you need scanned PDFs
TP_DEMO_MODE=true python -m termpilot --reload
```

- All settings are in `termpilot/settings.py`. Each field maps to a `TP_*` environment variable. Nested
  ones use a double underscore, e.g. `TP_MAIL_PROVIDERS__QQ__IMAP_HOST`.
- If `TP_SECRET_KEY` isn't set, a development key is generated on first start and saved to `var/secret.key`.
- The default database is SQLite (`var/termpilot.db`). Tables are created on startup.
- To work on the assistant without a real provider, run `python scripts/fake_model_server.py` and set
  `TP_LLM_BASE_URL=http://127.0.0.1:8100/v1`. It also answers `/v1/embeddings` with deterministic vectors.

### Tests and lint

```bash
pytest                          # 73 tests, ~15 s
ruff check termpilot tests scripts
ruff format termpilot tests scripts
```

The tests use an in-memory SQLite database, the demo campus gateway and a scripted chat model (see
`tests/conftest.py`). The clock is frozen on a Wednesday in week 6 of the autumn term, so anything that
depends on dates gives the same result every run.

`termpilot/knowledge/engine` is adapted from RAGFlow and keeps its original code style, so ruff skips it.

### Adding a tool to the assistant

1. Add a function to `termpilot/assistant/toolkit.py` with the `@tool(name, label, description, properties, required)` decorator.
2. Return `ToolOutcome(content, summary)`. If something is wrong and the model should know, raise one of
   the `AppError` subclasses.
3. If the tool changes data, don't do the change inside the tool. Call `ctx.propose(kind=..., payload=...)`
   and add an executor for that `kind` in `termpilot/assistant/approvals.py`.
4. Write a test with the scripted model in `tests/test_assistant.py`.

### Supporting another university

Implement the `CampusGateway` protocol in `termpilot/campus/gateway.py` and return your class from
`build_gateway`. The parsers in `academic_records.py` and `learning_platform.py` are plain functions, so
you can test them against saved responses the same way `tests/test_campus_parsers.py` does.

## Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000, talks to NUXT_PUBLIC_API_BASE (default http://localhost:8000)
npm test             # vitest
npm run typecheck    # vue-tsc in strict mode
npm run generate     # static build in .output/public
```

- On Windows, don't put the project in a folder whose path contains `#`. Vite reads it as a URL fragment
  and the build fails with confusing errors.
- Stores are imported explicitly (`~/stores/...`). Code in `app/utils` shouldn't use any Nuxt APIs, otherwise
  it can't be unit tested.
- Colours come from the tokens in `app/assets/css/main.css` (`bg-surface`, `text-muted`, `border-line`,
  `bg-brand`, ...). Dark mode mostly just redefines those tokens. The only `dark:` classes left are for
  text sitting on a brand-coloured background.
