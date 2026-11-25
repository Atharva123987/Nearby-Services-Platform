"""/api/v1/admin/* routes. Every route on this router requires an authenticated, active admin."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])
