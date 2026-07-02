from fastapi import FastAPI

app = FastAPI(title="CP-Backend")

@app.get("/health")
async def health():
    return {"status" : "ok"}
