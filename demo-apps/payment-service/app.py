from fastapi import FastAPI

app = FastAPI()

a=[]

for i in range(1, 1000000):
    a.append(i)

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