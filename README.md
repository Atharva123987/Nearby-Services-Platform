# Nearby Services Platform

[![CI](https://github.com/Atharva123987/Nearby-Services-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Atharva123987/Nearby-Services-Platform/actions/workflows/ci.yml)

Find hospitals, ATMs, shops and other services near you on a map. A FastAPI + PostGIS backend
answers radius searches in metres (nearest first, cached in Redis), and a Next.js frontend shows
them on a Leaflet map. Admins sign in to add, edit, delete and bulk-upload services.

| Map (clustered, filter by category) | Nearby search (radius, nearest first)         |
| ----------------------------------- | --------------------------------------------- |
| ![Map](docs/screenshots/map.png)    | ![Nearby search](docs/screenshots/nearby.png) |

![Service detail](docs/screenshots/service.png)

## Features

- **Map** (`/`): every service on a clustered map, filterable by category. Asks for your location
  and falls back to the default city (Nashik) if denied.
- **Nearby** (`/nearby`): pick a centre (your location or a map click) and a radius up to 50 km;
  results are listed nearest first with distances. The URL (`?lat=&lng=&radius=`) is shareable.
- **Service detail** (`/services/{id}`): mini map, directions link, metadata. Pages are
  statically regenerated (ISR) and revalidated when an admin edits a service.
- **Admin** (`/admin`): sign in, list/search, create/edit/delete with a map location picker,
  and bulk upload CSV/JSON in `partial` (keep good rows) or `strict` (all or nothing) mode.
- **API**: versioned under `/api/v1`, one JSON error envelope, request IDs, JSON logs,
  per-IP rate limits, Redis cache with version-based invalidation, `/health` and `/ready`.

## Tech stack

| Layer    | Stack                                                                                    |
| -------- | ---------------------------------------------------------------------------------------- |
| Backend  | Python 3.13, FastAPI, SQLAlchemy 2 (async) + GeoAlchemy2, Alembic, uv                    |
| Data     | PostgreSQL 16 + PostGIS 3.4 (`geography(Point, 4326)` + GiST index), Redis 7             |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind 4, React Query, Zustand, Leaflet |
| Tooling  | Docker Compose, ruff, black, mypy (strict), pytest, ESLint, Prettier, GitHub Actions     |

See [CLAUDE.md](CLAUDE.md) for the repository layout and layering rules
(`routes -> services -> repositories -> db` on the backend, `app/ -> features/` on the frontend).

## Quick start (Docker)

Requires Docker and `make` (or run the commands each target prints in the [Makefile](Makefile)).

```sh
make env       # create .env from .env.example (optional; compose has defaults)
make up        # build and start db, redis, api, web; waits until healthy
make migrate   # apply DB migrations
make seed      # load the sample dataset (500 services)
docker compose exec api python -m app.scripts.create_admin --email admin@example.com --password admin12345
```

| URL                          | What                            |
| ---------------------------- | ------------------------------- |
| http://localhost:3000        | Frontend                        |
| http://localhost:3000/admin  | Admin (sign in with demo creds) |
| http://localhost:8000/docs   | Swagger UI (not served in prod) |
| http://localhost:8000/health | Liveness                        |
| http://localhost:8000/ready  | Readiness (DB + Redis)          |

Ports are configurable with `WEB_PORT`, `API_PORT`, `POSTGRES_PORT` and `REDIS_PORT` in `.env`.

### Demo admin credentials

No admin exists by default. The command above creates one for local demos:

| Email               | Password     |
| ------------------- | ------------ |
| `admin@example.com` | `admin12345` |

Use your own values anywhere else (passwords must be at least 8 characters). The script is
safe to re-run and also reads `ADMIN_EMAIL` / `ADMIN_PASSWORD` from the environment.

## Quick start (local, without Docker for the app)

Requires Python 3.13 with [uv](https://docs.astral.sh/uv/) and Node 24. Postgres and Redis
still run in Docker.

```sh
make env
docker compose up -d db redis
make install                                   # uv sync, npm ci, pre-commit hooks
cd backend
uv run alembic upgrade head
uv run python -m app.scripts.seed ../data/sample_services.csv
uv run python -m app.scripts.create_admin --email admin@example.com --password admin12345
cd ..
make backend-dev                               # API on http://localhost:8000 (reload)
make frontend-dev                              # in another terminal: http://localhost:3000
```

The backend reads the repo-root `.env`; the frontend defaults to `http://localhost:8000` for
the API.

## Sample data

[`data/sample_services.csv`](data/sample_services.csv) and
[`data/sample_services.json`](data/sample_services.json) hold the same 500 services in Nashik
and Mumbai. `make seed` **replaces all services** with the CSV (refuses to run when
`APP_ENV=prod`). Either file can also be uploaded from the admin bulk upload page.

Bulk upload columns: `name`, `category` (`hospital` | `atm` | `shop` | `other`), `latitude`,
`longitude`, optional `rating` (0–5) and `metadata` (JSON object). Up to 5 MB / 10,000 rows. A
CSV template is at `GET /api/v1/admin/services/bulk/template`.

## API overview

| Method & path                              | Auth  | Purpose                                                         |
| ------------------------------------------ | ----- | --------------------------------------------------------------- |
| `GET /api/v1/services`                     | –     | Paginated list; `category`, `bbox` filters                      |
| `GET /api/v1/services/nearby`              | –     | `lat`, `lng`, `radius_km` (≤ 50), `category`, `limit`, `offset` |
| `GET /api/v1/services/{id}`                | –     | Service detail                                                  |
| `POST /api/v1/auth/login`, `/refresh`      | –     | Access + refresh JWTs                                           |
| `GET /api/v1/auth/me`                      | admin | Current admin                                                   |
| `GET/POST /api/v1/admin/services`          | admin | Search list / create                                            |
| `PATCH/DELETE /api/v1/admin/services/{id}` | admin | Update / delete                                                 |
| `POST /api/v1/admin/services/bulk`         | admin | CSV/JSON upload, `mode=partial\|strict`                         |

Errors always look like
`{"error": {"code", "message", "details", "request_id"}}`. Full schema at `/docs`.

## Environment variables

Every variable is documented in [`.env.example`](.env.example). Load order (later wins): code
defaults → `.env` → `.env.<APP_ENV>` → process environment. Under Docker Compose,
`DATABASE_URL` and `REDIS_URL` are overridden to use the service hostnames.

| Variable                                    | Default                                   | Purpose                                                         |
| ------------------------------------------- | ----------------------------------------- | --------------------------------------------------------------- |
| `APP_ENV`                                   | `dev`                                     | `dev` \| `test` \| `prod` (prod enforces the checks below)      |
| `APP_NAME`                                  | `Fieldguide API`                          | API title                                                       |
| `LOG_LEVEL`                                 | `INFO`                                    | Log level (JSON lines on stdout)                                |
| `POSTGRES_USER` / `_PASSWORD` / `_DB`       | `fieldguide`                              | Credentials for the compose `db` service                        |
| `DATABASE_URL`                              | `postgresql+asyncpg://…@localhost:5432/…` | Async SQLAlchemy URL                                            |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`          | `5` / `10`                                | Connection pool                                                 |
| `DB_CONNECT_TIMEOUT_SECONDS`                | `5`                                       | DB connect timeout                                              |
| `DB_ECHO`                                   | `false`                                   | Log every SQL statement                                         |
| `REDIS_URL`                                 | `redis://localhost:6379/0`                | Cache + rate-limit store                                        |
| `REDIS_SOCKET_TIMEOUT_SECONDS`              | `1`                                       | Redis timeout (cache is best-effort)                            |
| `JWT_SECRET`                                | placeholder                               | **Required in prod**: ≥ 32 chars, not the placeholder           |
| `JWT_ALGORITHM`                             | `HS256`                                   | Pinned; other algorithms are rejected                           |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`           | `30`                                      | Access token lifetime                                           |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`             | `7`                                       | Refresh token lifetime                                          |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD`            | empty                                     | Fallbacks for `create_admin`                                    |
| `RATE_LIMIT_ENABLED`                        | `true`                                    | Toggle rate limiting                                            |
| `RATE_LIMIT_DEFAULT_PER_MINUTE`             | `100`                                     | Every `/api/v1` route, per IP                                   |
| `RATE_LIMIT_NEARBY_PER_MINUTE`              | `30`                                      | `GET /services/nearby`                                          |
| `RATE_LIMIT_ADMIN_WRITE_PER_MINUTE`         | `60`                                      | Admin POST/PATCH/DELETE                                         |
| `RATE_LIMIT_LOGIN_PER_MINUTE` / `_PER_HOUR` | `5` / `20`                                | Login, per IP and per email                                     |
| `TRUSTED_PROXIES`                           | empty                                     | Proxy IPs/CIDRs whose `X-Forwarded-For` is trusted              |
| `CACHE_TTL_DEFAULT_SECONDS`                 | `300`                                     | Default cache TTL                                               |
| `CACHE_TTL_SEARCH_SECONDS`                  | `60`                                      | List / nearby results                                           |
| `CACHE_TTL_SERVICE_DETAIL_SECONDS`          | `600`                                     | Service detail                                                  |
| `CACHE_TTL_EMPTY_SECONDS`                   | `15`                                      | Empty results                                                   |
| `CORS_ORIGINS`                              | `http://localhost:3000`                   | Comma-separated; `*` is rejected in prod                        |
| `READY_CHECK_TIMEOUT_SECONDS`               | `2`                                       | Per-dependency timeout for `/ready`                             |
| `API_PORT` / `WEB_PORT`                     | `8000` / `3000`                           | Published host ports                                            |
| `POSTGRES_PORT` / `REDIS_PORT`              | `5432` / `6379`                           | Published host ports                                            |
| `NEXT_PUBLIC_API_URL`                       | `http://localhost:8000`                   | API URL for the browser (baked in at build time)                |
| `API_INTERNAL_URL`                          | `NEXT_PUBLIC_API_URL`                     | API URL for Next server-side calls (compose: `http://api:8000`) |

## Development

```sh
make lint        # ruff + black, eslint + prettier
make typecheck   # mypy (strict) + tsc
make test        # pytest
make format      # auto-fix formatting
make help        # list all targets
```

Integration tests run against a real, migrated PostGIS database and Redis and are skipped
unless both are set (each test rolls back its transaction and **flushes** the Redis DB):

```sh
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://fieldguide:fieldguide@localhost:5432/fieldguide \
TEST_REDIS_URL=redis://localhost:6379/15 uv run pytest
```

[CI](.github/workflows/ci.yml) runs backend lint, mypy, migrations and pytest against PostGIS +
Redis service containers, frontend lint, format check, tsc and build, then builds both Docker
images. It uses test values only, so no secrets are needed.

## Known limitations

- **No token revocation.** JWTs are stateless; logout clears the httpOnly cookies, but a stolen
  token stays valid until it expires.
- **Single admin role.** Every admin can do everything; there are no public user accounts.
- **Fixed-window rate limiting.** Simple and cheap, but a client can send up to twice the limit
  across a window boundary.
- **Coarse cache invalidation.** Any write bumps one version key, so all cached lists and nearby
  results are dropped at once.
- **No antimeridian bounding boxes.** `bbox` with `min_lng > max_lng` is rejected (radius search
  across the antimeridian does work).
- **Sample data is two cities** with the map defaulting to Nashik; there is no geocoding or
  address search.
- **No frontend tests** yet; the frontend is covered by lint, type checks and the build.
- **`make seed` deletes all services** before loading the sample file (dev only).

## What I'd do with more time

- Frontend component and end-to-end tests (Vitest + Testing Library, Playwright).
- Refresh-token rotation with a server-side denylist, and audit logs for admin changes.
- Address search / geocoding and "open now" filtering from metadata.
- Sliding-window rate limits and finer-grained cache invalidation (by area or category).
- Publish Docker images from CI and add a deploy pipeline with a staging environment.
- Metrics and tracing (Prometheus / OpenTelemetry) alongside the JSON logs.
