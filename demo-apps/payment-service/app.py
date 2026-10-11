from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {
        "service": "payment-service",
        "version": "v1"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }