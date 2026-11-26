# Nearby Services Platform

[![CI](https://github.com/Atharva123987/Nearby-Services-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Atharva123987/Nearby-Services-Platform/actions/workflows/ci.yml)

FastAPI + PostGIS + Redis backend and a Next.js frontend for finding services near a location.
See [CLAUDE.md](CLAUDE.md) for the architecture.

## Quick start

```sh
make env       # create .env from .env.example
make up        # start db, redis, api, web
make migrate   # apply DB migrations
make seed      # optional sample data
```

## Checks

```sh
make lint typecheck test
```

Integration tests need a migrated PostGIS DB and a spare Redis DB (it is flushed):
`TEST_DATABASE_URL=postgresql+asyncpg://... TEST_REDIS_URL=redis://localhost:6379/15`.
CI (`.github/workflows/ci.yml`) runs backend lint/mypy/pytest against PostGIS + Redis service
containers, frontend lint/format/tsc/build, and builds both Docker images.
