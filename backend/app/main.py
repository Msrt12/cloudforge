from fastapi import FastAPI

from .database import Base, engine
from . import models
from .routers import applications


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CloudForge API"
)

app.include_router(applications.router)


@app.get("/")
def root():
    return {
        "message": "CloudForge API is running"
    }