from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(title="Fieldguide API")
app.include_router(health.router)
