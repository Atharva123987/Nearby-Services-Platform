# Nearby Services Platform

[![CI](https://github.com/Atharva123987/Nearby-Services-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Atharva123987/Nearby-Services-Platform/actions/workflows/ci.yml)

**Fieldguide** finds hospitals, ATMs, shops and other services near a point on a map. A FastAPI +
PostGIS backend answers radius searches in metres (nearest first, cached in Redis), and a
Next.js + Leaflet frontend shows the results on a map and in a list. Admins sign in to add,
edit, delete and bulk-upload services.

| All services, nearest first               | Radius search (3 km)                          |
| ----------------------------------------- | --------------------------------------------- |
| ![Overview map](docs/screenshots/map.png) | ![Radius search](docs/screenshots/nearby.png) |

![Service detail page](docs/screenshots/service.png)

## Features

- **Nearby search** (`/`): pick a centre with **Use my location**, by clicking the map, or with
  the Mumbai / Nashik shortcuts (the default is Nashik). Results are listed nearest first with
  distances, 20 at a time, and shown as clustered category pins. Optionally limit the search to a
  1–50 km radius and filter by category. The URL (`?lat=&lng=&radius=&category=`, with
  `radius=all` for no limit) can be shared. The old `/nearby` route redirects here.
- **Service detail** (`/services/{id}`): mini map, Google Maps directions link and the service's
  metadata. Pages are cached by Next (ISR, 60 s) and revalidated as soon as an admin edits or
  deletes the service.
- **Admin** (`/admin`): sign in, see counts per category, search and page through services,
  create or edit with a map location picker, delete, and bulk upload CSV/JSON in `partial`
  (keep the good rows) or `strict` (all or nothing) mode with per-row errors.
- **API**: versioned under `/api/v1`, one JSON error envelope, request IDs, JSON logs, per-IP
  rate limits, Redis cache with version-based invalidation, and `/health` + `/ready` probes.

## Tech stack

| Layer    | Stack                                                                                                     |
| -------- | --------------------------------------------------------------------------------------------------------- |
| Backend  | Python 3.13, FastAPI, SQLAlchemy 2 (async) + GeoAlchemy2, Alembic, PyJWT + bcrypt, uv                     |
| Data     | PostgreSQL 16 + PostGIS 3.4 (`geography(Point, 4326)` + GiST index), Redis 7                              |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind 4, React Query, Zustand, Leaflet + MapLibre (CARTO basemap) |
| Tooling  | Docker Compose, ruff, black, mypy (strict), pytest, ESLint, Prettier, pre-commit, GitHub Actions          |

## Quick start (Docker)

Requires Docker with Compose v2 and `make` (without `make`, run the commands from the
[Makefile](Makefile) directly).

```sh
make env       # create .env from .env.example (optional; compose has defaults)
make up        # build and start db, redis, api, web; waits until healthy
make migrate   # apply DB migrations (alembic upgrade head)
make seed      # load the sample dataset (500 services)
docker compose exec api python -m app.scripts.create_admin --email admin@example.com --password admin12345
```

| URL                          | What                                     |
| ---------------------------- | ---------------------------------------- |
| http://localhost:3000        | Frontend (nearby search)                 |
| http://localhost:3000/admin  | Admin (sign in with the demo creds)      |
| http://localhost:8000/docs   | Swagger UI                               |
| http://localhost:8000/health | Liveness                                 |
| http://localhost:8000/ready  | Readiness (DB required, Redis optional)  |

Ports are configurable with `WEB_PORT`, `API_PORT`, `POSTGRES_PORT` and `REDIS_PORT` in `.env`.
If you change `API_PORT` or `WEB_PORT`, also update `NEXT_PUBLIC_API_URL` and `CORS_ORIGINS` to
match, then rebuild the frontend with `make up` (the API URL is baked in at build time).

### Demo admin credentials

No admin exists by default. The last command above creates one for local demos:

| Email               | Password     |
| ------------------- | ------------ |
| `admin@example.com` | `admin12345` |

Use your own values anywhere else (passwords must be at least 8 characters). The script is
safe to re-run (it exits cleanly if the admin already exists) and falls back to
`ADMIN_EMAIL` / `ADMIN_PASSWORD` from the environment, then to an interactive prompt.

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

The backend reads the repo-root `.env`. Next.js only reads env files from `frontend/`, so put
any frontend overrides (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CARTO_BASEMAP_KEY`,
`API_INTERNAL_URL`) in `frontend/.env.local`; without it the frontend uses
`http://localhost:8000` for the API.

## Sample data

[`data/sample_services.csv`](data/sample_services.csv) and
[`data/sample_services.json`](data/sample_services.json) hold the same 500 services across
Nashik and Mumbai (133 hospitals, 100 ATMs, 142 shops, 125 other). Docker Compose mounts
`data/` read-only at `/data` in the API container. `make seed` **replaces all services** with
the CSV in strict mode and refuses to run when `APP_ENV=prod`. Either file can also be uploaded
from the admin bulk upload page.

Bulk upload columns: `name`, `category` (`hospital` | `atm` | `shop` | `other`, case-insensitive),
`latitude`, `longitude`, optional `rating` (0–5, one decimal place) and `metadata` (JSON object,
at most 10 KB). Files are limited to 5 MB / 10,000 rows. A CSV template is served at
`GET /api/v1/admin/services/bulk/template`; small example files are in
[`docs/postman/samples/`](docs/postman/samples).

## API overview

| Method & path                                  | Auth  | Purpose                                                                      |
| ---------------------------------------------- | ----- | ---------------------------------------------------------------------------- |
| `GET /health`, `GET /ready`                    | –     | Liveness / readiness (never rate limited)                                    |
| `GET /api/v1/services`                         | –     | Paginated list, newest first; `category`, `bbox` filters                     |
| `GET /api/v1/services/nearby`                  | –     | `lat`, `lng`, `radius_km` (≤ 50), `category`, `limit`, `offset`; with distances |
| `GET /api/v1/services/nearby/markers`          | –     | Every matching pin, nearest first; `radius_km` (≤ 50) or `all` (used by the UI) |
| `GET /api/v1/services/{id}`                    | –     | Service detail                                                               |
| `POST /api/v1/auth/login`, `/auth/refresh`     | –     | Access + refresh JWTs                                                        |
| `GET /api/v1/auth/me`                          | admin | Current admin                                                                |
| `GET/POST /api/v1/admin/services`              | admin | Search list / create (409 if the same name exists within 10 m)               |
| `PATCH/DELETE /api/v1/admin/services/{id}`     | admin | Update / delete                                                              |
| `POST /api/v1/admin/services/bulk`             | admin | CSV/JSON upload, `mode=partial\|strict`                                      |
| `GET /api/v1/admin/services/bulk/template`     | admin | CSV template                                                                 |

Errors always look like `{"error": {"code", "message", "details", "request_id"}}`. Public reads
return `X-Cache: HIT|MISS`; rate-limited routes return `X-RateLimit-*` headers and `Retry-After`
on 429. Explore the API in Swagger UI at `/docs` or retrieve the schema at `/openapi.json`. A Postman collection and local environment are in
[`docs/postman/`](docs/postman) (it does not include `/services/nearby/markers` yet; set
`adminPassword` in the environment before running the admin requests).

## Environment variables

Every variable is documented in [`.env.example`](.env.example). Load order (later wins): code
defaults → `.env` → `.env.<APP_ENV>` → process environment. Under Docker Compose, `DATABASE_URL`
and `REDIS_URL` are overridden to use the service hostnames.

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
| `JWT_SECRET`                                | placeholder                               | **Required in prod**: ≥ 32 chars, not a known default           |
| `JWT_ALGORITHM`                             | `HS256`                                   | Pinned; other algorithms are rejected                           |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`           | `30`                                      | Access token lifetime                                           |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`             | `7`                                       | Refresh token lifetime                                          |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD`            | empty                                     | Fallbacks for `create_admin`                                    |
| `RATE_LIMIT_ENABLED`                        | `true`                                    | Toggle rate limiting                                            |
| `RATE_LIMIT_DEFAULT_PER_MINUTE`             | `100`                                     | Every `/api/v1` route, per IP                                   |
| `RATE_LIMIT_NEARBY_PER_MINUTE`              | `30`                                      | `/services/nearby` and `/services/nearby/markers`               |
| `RATE_LIMIT_ADMIN_WRITE_PER_MINUTE`         | `60`                                      | Admin POST/PATCH/DELETE                                         |
| `RATE_LIMIT_LOGIN_PER_MINUTE` / `_PER_HOUR` | `5` / `20`                                | Login, per IP and per email (fails closed if Redis is down)     |
| `TRUSTED_PROXIES`                           | empty                                     | Proxy IPs/CIDRs whose `X-Forwarded-For` is trusted              |
| `CACHE_TTL_DEFAULT_SECONDS`                 | `300`                                     | Public list                                                     |
| `CACHE_TTL_SEARCH_SECONDS`                  | `60`                                      | Nearby results and markers                                      |
| `CACHE_TTL_SERVICE_DETAIL_SECONDS`          | `600`                                     | Service detail                                                  |
| `CACHE_TTL_EMPTY_SECONDS`                   | `15`                                      | Empty results                                                   |
| `CORS_ORIGINS`                              | `http://localhost:3000`                   | Comma-separated; `*` is rejected in prod                        |
| `READY_CHECK_TIMEOUT_SECONDS`               | `2`                                       | Per-dependency timeout for `/ready`                             |
| `API_PORT` / `WEB_PORT`                     | `8000` / `3000`                           | Published host ports                                            |
| `POSTGRES_PORT` / `REDIS_PORT`              | `5432` / `6379`                           | Published host ports                                            |
| `NEXT_PUBLIC_API_URL`                       | `http://localhost:8000`                   | API URL for the browser (baked in at build time)                |
| `NEXT_PUBLIC_CARTO_BASEMAP_KEY`             | empty                                     | CARTO key sent with basemap requests (baked in at build time)   |
| `API_INTERNAL_URL`                          | `NEXT_PUBLIC_API_URL`                     | API URL for Next server-side calls (compose: `http://api:8000`) |

## Project structure

```
backend/            FastAPI service
  app/api/          routes: /health + /ready, and /api/v1 (auth, services, admin)
  app/services/     business rules, caching, bulk upload parsing
  app/repositories/ all SQL / PostGIS queries
  app/models/       SQLAlchemy + GeoAlchemy2 models
  app/schemas/      Pydantic request/response contracts and validation
  app/core/         settings, JSON logging, error envelope, rate limiting, security
  app/scripts/      create_admin, seed
  alembic/          migrations (what `make migrate` applies)
  tests/            unit (fake repositories) and integration (real PostGIS + Redis)
frontend/src/
  app/              routes only: pages, layouts, route handlers (auth cookies, API proxy)
  features/         map, services, admin: each with api.ts (query fns + keys) and components/
  lib/              API client (maps the error envelope to ApiError), auth, config
  stores/           Zustand UI/map state
db/migrations/      hand-written SQL schema (reference for the models)
data/               sample datasets
docs/               screenshots, Postman collection
```

The backend is layered `routes -> services -> repositories -> db`: routes only handle HTTP,
services hold business rules and caching, and repositories own the queries, so services are
unit-tested with fake repositories. On the frontend, `app/` stays thin and composes `features/`;
server state goes through React Query and UI state through Zustand. Admin tokens live in
httpOnly cookies and admin API calls go through a Next route handler (`/api/backend/*`), so
page JavaScript never sees a token.

## Development

```sh
make lint        # ruff + black, eslint + prettier
make typecheck   # mypy (strict) + tsc
make test        # pytest
make format      # auto-fix formatting
make help        # list all targets
```

Integration tests run against a real, migrated PostGIS database (`TEST_DATABASE_URL`) and, for
the API tests, Redis (`TEST_REDIS_URL`); they are skipped when those are not set. Each test
rolls back its transaction, and the API tests **flush** the Redis DB, so use a spare one:

```sh
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://fieldguide:fieldguide@localhost:5432/fieldguide \
TEST_REDIS_URL=redis://localhost:6379/15 uv run pytest
```

[CI](.github/workflows/ci.yml) runs backend lint, mypy, migrations and pytest against PostGIS +
Redis service containers, frontend lint, format check, tsc and build, then builds both Docker
images. It uses test values only, so no secrets are needed.

## Known limitations

- **Markers are not paginated.** `GET /services/nearby/markers` returns every matching pin, and
  with no radius limit that is every service. Fine for the 500-row sample, but it will not scale
  to a large dataset.
- **No token revocation.** JWTs are stateless; logout clears the httpOnly cookies, but a stolen
  token stays valid until it expires.
- **Single admin role, created from the CLI.** Every admin can do everything, there is no UI to
  manage admins, and there are no public user accounts.
- **Bulk upload only checks duplicates inside the file.** Creating a single service rejects the
  same name within 10 m; a bulk upload does not compare against existing services.
- **Fixed-window rate limiting.** Simple and cheap, but a client can send up to twice the limit
  across a window boundary.
- **Coarse cache invalidation.** Any write bumps one version key, so all cached lists, nearby
  results and markers are dropped at once.
- **No antimeridian bounding boxes.** `bbox` with `min_lng > max_lng` is rejected (radius search
  across the antimeridian does work).
- **Two cities, no address search.** The sample data covers Nashik and Mumbai only, and there is
  no geocoding. "Use my location" needs HTTPS or `localhost` (a browser rule).
- **Third-party basemap.** Map tiles come from CARTO's hosted service; there is no fallback
  provider if it is unreachable.
- **No frontend tests** yet; the frontend is covered by lint, type checks and the build.
- **`make seed` deletes all services** before loading the sample file (dev only).

## What I'd do with more time

- Cap or cluster markers on the server (or serve vector tiles) so the map scales past a few
  thousand services.
- Frontend component and end-to-end tests (Vitest + Testing Library, Playwright).
- Refresh-token rotation with a server-side denylist, admin roles, and audit logs for admin
  changes.
- Address search / geocoding and "open now" filtering from metadata.
- Sliding-window rate limits and finer-grained cache invalidation (by area or category).
- Publish Docker images from CI and add a deploy pipeline with a staging environment.
- Metrics and tracing (Prometheus / OpenTelemetry) alongside the JSON logs.
