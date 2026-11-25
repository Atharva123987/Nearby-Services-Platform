"""/api/v1 routers."""

from fastapi import APIRouter, Depends

from app.api.deps import default_rate_limit
from app.api.v1 import admin, auth, services

# Health endpoints live outside this router, so they are never rate limited.
api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(default_rate_limit)])
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(services.router)
