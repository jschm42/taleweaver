from fastapi import FastAPI

app = FastAPI(
    title="TaleWeaver",
    description="Backend API for TaleWeaver",
    version="0.1.0",
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
