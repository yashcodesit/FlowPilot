
from fastapi import FastAPI

app = FastAPI(
    title="FlowPilot API",
    description="AI-powered workflow planning and management",
    version="0.1.0",
)


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
