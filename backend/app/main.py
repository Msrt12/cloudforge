from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .database import Base, engine
from . import models
from .routers import applications


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CloudForge API"
)

app.include_router(applications.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/healthz", include_in_schema=False)
def health_check():
    return {"status": "healthy"}
