# CP Platform — Competitive Programming Judge (Backend)

A backend REST API for an online judge, similar in spirit to Codeforces or Codeforces-lite. Users register, browse problems, submit code, and get it compiled and run inside an isolated Docker sandbox against hidden test cases — with results delivered asynchronously through a background job queue.

This is a backend-only project (no frontend). All interaction happens through the REST API, documented interactively via Swagger UI at `/docs`.

## Why this project exists

Most CRUD-app projects stop at "store data, return data." This one goes a step further: it actually **executes untrusted, user-submitted code safely**, which is a real systems problem — running arbitrary code without letting it access the network, exhaust memory, fork-bomb the host, or run forever. The interesting engineering here isn't the CRUD routes; it's the sandbox and the async pipeline around it.

## Features

- **JWT-based authentication** — registration, login, and route-level guards for authenticated/admin-only access
- **Admin-gated problem management** — only admins can create/delete problems
- **Hidden vs. sample test cases** — like a real judge, only sample test cases are ever exposed through the API; hidden ones stay server-side and are used only during judging
- **Sandboxed code execution** — submitted C++/Python code compiles and runs inside a Docker container with:
  - No network access (`--network none`)
  - Memory and CPU limits (`--memory`, `--cpus`)
  - Process limits (`--pids-limit`, prevents fork bombs)
  - Read-only filesystem (`--read-only`)
  - A hard wall-clock timeout
- **Six real verdicts**: `AC` (Accepted), `WA` (Wrong Answer), `TLE` (Time Limit Exceeded), `MLE` (Memory Limit Exceeded), `RE` (Runtime Error), `CE` (Compilation Error)
- **Async job queue** — submissions are judged by background worker tasks, not synchronously inside the HTTP request, so the API responds immediately (`202 Accepted`) regardless of how long judging takes
- **Crash recovery** — on startup, any submission left `PENDING`/`RUNNING` from before a restart is automatically re-enqueued, so a server crash never silently loses a submission
- **Sliding-window rate limiting** — caps submissions per user per minute, without the boundary-burst flaw of a naive fixed-window counter
- **Leaderboard** — ranks users by distinct problems solved, with ICPC-style tiebreaking on total time across accepted submissions, computed in a single aggregate SQL query

## Tech stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 (async) via `asyncpg` |
| Validation | Pydantic v2 |
| Auth | JWT (`python-jose`) + bcrypt |
| Sandboxing | Docker |
| Concurrency | `asyncio` (queue + background workers) |
| Language | Python 3.12 |

## Architecture

```
Client (curl / Swagger UI)
        │
        ▼
  FastAPI app (Uvicorn)
        │
   ┌────┼──────────────────────────┐
   │    │                          │
 Auth  Problems CRUD        Submission endpoint
   │    │                          │
   └────┴─────────────┬────────────┘
                       ▼
              PostgreSQL (async SQLAlchemy)
                       │
             submission saved as PENDING
                       ▼
             asyncio.Queue (in-memory)
                       │
                       ▼
            Background worker task(s)
                       │
                       ▼
          Docker sandbox (compile → run)
       compare stdout against expected output
                       │
                       ▼
         Verdict written back to PostgreSQL
                       │
                       ▼
       Client polls GET /submissions/{id}
```

**Why an async queue instead of judging synchronously inside the request?** Compiling and running code can take real time. Blocking an HTTP request on that would tie up a connection per in-flight submission and make the API feel unresponsive under any concurrent load. Instead, `POST /submissions` does the minimal work (validate, insert, enqueue) and returns immediately; a fixed pool of background workers pulls submissions off the queue and judges them independently, so multiple submissions can be judged concurrently without blocking new requests from coming in.

**Known limitation, worth being upfront about:** both the job queue and the rate limiter currently live in a single process's memory. This is why a crash-recovery sweep exists (to survive a *restart* of that one process), but it would **not** work correctly across multiple server replicas behind a load balancer — each replica would track its own separate queue and rate-limit counters. The natural next step at scale would be moving both to Redis (a shared queue via Redis Streams/lists, rate limiting via Redis sorted sets) so state is shared across replicas instead of trapped in one process.

## Database schema

Four tables, related by foreign key:

- **`users`** — `id`, `username`, `email`, `password_hash`, `is_admin`, `created_at`
- **`problems`** — `id`, `title`, `description`, `time_limit_ms`, `memory_limit_mb`, `created_by → users.id`, `created_at`
- **`test_cases`** — `id`, `problem_id → problems.id (ON DELETE CASCADE)`, `input_data`, `expected_output`, `is_sample`
- **`submissions`** — `id`, `user_id → users.id`, `problem_id → problems.id`, `code`, `language`, `status`, `verdict`, `time_ms`, `memory_kb`, `submitted_at`

`language` and `verdict` are backed by real Postgres `ENUM` types, so the database itself rejects any value outside the defined set — not just application-level validation.

## API overview

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Register a new user |
| POST | `/auth/login` | — | Log in, receive a JWT |
| POST | `/problems` | Admin | Create a problem with test cases |
| GET | `/problems` | — | List all problems |
| GET | `/problems/{id}` | — | Get a problem (sample test cases only) |
| DELETE | `/problems/{id}` | Admin | Delete a problem |
| POST | `/submissions` | User | Submit code for judging |
| GET | `/submissions/{id}` | Owner/Admin | Poll a submission's status/verdict |
| GET | `/submissions` | User | List your own submission history |
| GET | `/leaderboard` | — | Ranked leaderboard |
| GET | `/health` | — | Health check |

Full interactive documentation, including request/response schemas, is available at `/docs` once the server is running.

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL
- Docker (with your user in the `docker` group — `sudo usermod -aG docker $USER`, then log out/in)

### Installation

```bash
git clone <this-repo-url>
cd cp-platform
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:<port>/<dbname>
SECRET_KEY=<a-long-random-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=60
MAX_SUBMISSIONS_PER_MINUTE=3
```

### Docker images

Pull the images used for compiling/running submissions ahead of time:

```bash
docker pull gcc:13
docker pull python:3.12-slim
```

### Run

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API docs. Tables are created automatically on first startup.

### Making a user an admin

There's no API endpoint for this by design — a client should never be able to self-promote. Do it directly in the database:

```sql
UPDATE users SET is_admin = true WHERE username = 'your_username';
```

## Notable design decisions

- **Sliding-window rate limiting**, not fixed-window — a fixed window resets at a clean boundary (e.g. every 60s), which lets a user burst right at the edge of two windows and effectively double their limit in a short span. A sliding window (a per-user timestamp deque, pruned to the last 60 seconds on every check) closes that loophole entirely.
- **Hidden test cases never leave the server** — the API only ever returns `sample_test_cases` in a problem's response; the full test case set (including hidden ones) is only read internally by the judge worker.
- **`HTTPBearer` over `OAuth2PasswordBearer`** — the latter's Swagger "Authorize" flow expects a username/password form POST to the token URL, which doesn't match this API's JSON-based login endpoint. `HTTPBearer` gives a simple paste-a-token field instead, matching how the API is actually meant to be used.
