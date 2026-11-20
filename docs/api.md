# API reference

[中文版](api.zh-CN.md)

While the backend is running, FastAPI serves interactive docs at `/docs` (Swagger UI) and `/redoc`. Those
are always up to date with the code. This page is the short version, plus the conventions that aren't
obvious from Swagger.

## General rules

- Everything is under `/api`, and requests and responses are JSON unless noted otherwise.
- Auth: send `Authorization: Bearer <token>`, using the token from `POST /api/auth/session`. Tokens last
  `TP_TOKEN_TTL_MINUTES` (12 hours by default). `DELETE /api/auth/session` revokes all of them at once.
- Errors always look like this:

  ```json
  {"error": {"code": "not_found", "message": "...", "details": null}}
  ```

  Codes you'll see: `invalid_input` (422), `not_authenticated`, `invalid_credentials` and
  `campus_session_expired` (401), `not_found` (404), `conflict` (409), `upstream_failure` (502),
  `feature_unavailable` (503).
- Timestamps are ISO 8601 with an offset. Times of day are `HH:MM`. Weekdays go from 1 (Monday) to 7 (Sunday).

## Accounts

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/config` | Public feature flags: `demo_mode`, `assistant`, `library`, `web_search` |
| POST | `/auth/session` | Log in with `{username, password}`. Returns `{token, expires_in, first_visit, student}` |
| DELETE | `/auth/session` | Log out everywhere |
| GET, PATCH | `/me` | Profile. PATCH accepts `interests`, `term_start` or `clear_term_start` |
| GET | `/me/term` | Current term: `today`, `label`, `start`, `end`, `weeks`, `current_week`, `in_session` |
| GET | `/me/photo` | Profile photo as `{data_url}` |

## Planning

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/briefing` | Data for the Today page: classes, next class, due soon, overdue, clashes, counters, tips |
| GET | `/timetable` | `{term, entries, clashes}` |
| POST, PATCH, DELETE | `/timetable`, `/timetable/{id}` | Manage entries (`title`, `kind`, `weekday`, `starts_at`, `ends_at`, `weeks`, `location`, ...) |
| GET | `/tasks?status=open\|done\|all` | Tasks, sorted by due date |
| POST, PATCH, DELETE | `/tasks`, `/tasks/{id}` | Manage tasks. `due_at` has to include a timezone offset |
| POST | `/planner/suggestions` | `{days, block_minutes, day_start, day_end}`, returns suggested study blocks |
| POST | `/planner/accept` | `{blocks: [{task_id, day, starts_at, ends_at}]}`, returns the created entries |
| GET | `/calendar/link` | Private subscription URL, valid for 180 days or until you log out |
| GET | `/calendar/feed.ics?token=...` | The iCalendar feed itself. No bearer header needed, the token is in the URL |

## Campus data

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/sync` | Run an import. Optional `{sources: [...]}` with any of `profile`, `grades`, `timetable`, `deadlines`, `coursework`, `materials` |
| GET | `/sync/runs` | Recent runs, with one result per source |
| GET | `/academics` | GPA, rank, credits by category, coursework grades grouped by course |
| GET | `/academics/materials` | Links to course files |

## Mail

| Method | Path | What it does |
| --- | --- | --- |
| GET, PUT, DELETE | `/mail/account` | Connection status / connect with `{provider, address, secret}` / disconnect |
| POST | `/mail/sync` | `{folder, limit, unread_only}`, returns `{fetched, added, updated}` |
| GET | `/mail/messages?folder&unread_only&q&limit` | Message list |
| GET | `/mail/messages/{id}` | One message, with text and HTML bodies |
| POST | `/mail/messages/{id}/tasks` | Deadlines found in the message. Nothing is saved |
| POST | `/mail/send` | `{to, cc, bcc, subject, body}` |

## Assistant

| Method | Path | What it does |
| --- | --- | --- |
| GET, POST | `/conversations` | List (search with `q`) or create |
| GET, PATCH, DELETE | `/conversations/{id}` | Turns, attachments and proposals / rename / delete |
| POST | `/conversations/{id}/ask` | `{question, mode: agent\|ask\|research, deep_think}`, returns an event stream |
| POST, DELETE | `/conversations/{id}/attachments`, `.../attachments/{attachment_id}` | Attach a file (multipart, field `file`) or remove it |
| GET | `/approvals?state=pending\|all` | Proposals made by the assistant |
| POST | `/approvals/{id}/decision` | `{approve: true\|false}`, returns the proposal with its outcome |

### The answer stream

`POST /conversations/{id}/ask` responds with `text/event-stream`. The `data` of every event is a JSON object.

| Event | Data | Meaning |
| --- | --- | --- |
| `turn` | `{turn_id, conversation_id, mode}` | Always the first event |
| `step` | `{id, tool, label, status, detail}` | Tool progress: `running`, then `done` or `failed` |
| `sources` | `{items: [{index, kind, title, excerpt, url}]}` | Evidence. The answer cites it as `[index]` |
| `reasoning` | `{text}` | Thinking text from a reasoning model, streamed |
| `answer` | `{text}` | The answer, streamed |
| `approval` | `{id, kind, title, summary, preview, status, expires_at}` | A proposal waiting for a decision |
| `suggestions` | `{items}` | Follow-up questions |
| `title` | `{title}` | The conversation got a generated title |
| `error` | `{message}` | Something failed. The stream still ends with `done` |
| `done` | `{turn_id}` | Always the last event |

## Library and workspace

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/library/documents` | `{available, reason, documents}` |
| POST | `/library/documents` | Upload (multipart, field `files`, can repeat). Returns `{uploaded, failed}` |
| DELETE | `/library/documents/{id}` | Remove from the index and from disk |
| POST | `/library/documents/{id}/study-aid` | `{kind: summary\|quiz\|flashcards}`, returns an event stream (`answer`, `error`, `done`) |
| GET | `/workspace/files?folder=.` | `{files, usage_bytes, quota_bytes}` |
| POST | `/workspace/files?folder=.&replace=false` | Upload (multipart, field `file`) |
| GET | `/workspace/download?path=...` | Download a file |
| DELETE | `/workspace/files?path=...` | Move a file to the workspace trash |

## Health

`GET /health` returns `{status, version, database, search, assistant}`. `search` is `null` when the
library isn't configured.
