from fastapi import FastAPI

app = FastAPI(title="EdgeFlow AI Control Plane & API")

@app.get("/")
def root():
    return {"service": "edgeflow-api", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
