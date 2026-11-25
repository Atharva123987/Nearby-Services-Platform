"""/api/v1 routers."""

from fastapi import APIRouter

from app.api.v1 import services

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(services.router)
