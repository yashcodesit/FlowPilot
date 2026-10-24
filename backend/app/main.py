from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routes.workflows import router as workflows_router
from app.routes.tasks import router as tasks_router
from app.routes.dependencies import router as dependencies_router
from app.routes.scheduling import router as scheduling_router
from app.routes.generation import router as generation_router

app = FastAPI(
    title="FlowPilot API",
    description="AI-powered workflow planning and management",
    version="0.1.0",
)

app.include_router(workflows_router)
app.include_router(tasks_router)
app.include_router(dependencies_router)
app.include_router(scheduling_router)
app.include_router(generation_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to FlowPilot API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "FlowPilot API",
    }


@app.get("/health/db")
def database_health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "database": "connected",
    }