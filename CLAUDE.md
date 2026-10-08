# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Reflective Research Agent: a FastAPI app that turns a user prompt into a multi-step research workflow (planner → research/writer/editor agents) and returns a Markdown report. There are no tests and no linter configured.

## Commands

The intended runtime is a single Docker container running Postgres + Uvicorn (`docker/entrypoint.sh`):

```bash
docker build -t fastapi-postgres-service .
docker run --rm -it -p 8000:8000 -p 5432:5432 --name fpsvc --env-file .env fastapi-postgres-service
```

- `.env` must contain `OPENAI_API_KEY` and `TAVILY_API_KEY`.
- UI at http://localhost:8000/, Swagger at `/docs`, health check at `/api`.
- Running outside Docker: needs `DATABASE_URL` (a Postgres DSN) set, then `uvicorn main:app --reload`. `main.py` raises at import if it is unset.
- Exercise the API: `POST /generate_report` with `{"prompt": "..."}` → `{task_id}`; poll `GET /task_progress/{id}` and `GET /task_status/{id}`.

## Architecture

- `main.py` — FastAPI app, SQLAlchemy `Task` model, and `run_agent_workflow`. `/generate_report` calls `planner_agent` synchronously, then runs the plan in a `threading.Thread`.
- `src/planning_agent.py` — `planner_agent` asks an LLM for a Python list of ≤7 step strings, then `_ensure_contract` forces a fixed shape: step 1 = Tavily search, step 2 = arXiv lookup, last step = writer producing the final report. Those exact strings are hard-coded, so edit them there if the workflow changes. `executor_agent_step` builds a context from the history and routes each step to an agent by **keyword-matching the step text** ("research", "draft"/"write", "revise"/"edit"/"feedback"); anything else raises `ValueError`. Planner prompts and step wording must keep these keywords.
- `src/agents.py` — `research_agent` (tool-calling with the Tavily, arXiv and Wikipedia tools), `writer_agent` and `editor_agent`. All use `aisuite.Client` with model strings like `openai:gpt-4.1-mini`. The planner defaults to `openai:o4-mini`.
- `src/research_tools.py` — the tool functions passed to the LLM: `tavily_search_tool`, `arxiv_search_tool` (can download PDFs and extract text) and `wikipedia_search_tool`.
- The final report is the output of the **last** step in the execution history. It is stored as JSON in `Task.result` as `{html_report, history}`.

## Gotchas

- **Progress state lives in memory.** `task_progress` is a module-level dict in `main.py`, so it is lost on restart and is not shared across Uvicorn workers. Only the final status and result are in Postgres.
- **`main.py` calls `Base.metadata.drop_all` on every startup**, which wipes all tasks. The README suggests guarding it with an env flag.
- The `PromptRequest` model only accepts `prompt`. The README's `model` field in the curl example is ignored.
- `main.py` checks `DATABASE_URL.startswith(...)` before the `if not DATABASE_URL` check, so a missing `DATABASE_URL` raises `AttributeError` rather than the intended `RuntimeError`.
- `executor_agent_step` unpacks history entries as `(desc, agent, output)`, but `run_agent_workflow` stores `[plan_step_title, actual_step_description, output]`. The agent-type context labels in that function are therefore effectively keyed on the step title only.
