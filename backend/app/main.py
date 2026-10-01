from fastapi import FastAPI
from  datetime import datetime
import uvicorn

app = FastAPI(
    title="Backend API",
    description="API for the backend",
    version="1.0.0",
)


@app.get("/")
def index():
    return {"message": "Debrief API is operational"}

@app.get("/health")
def health():
    
    return {
        "status": "ok",
        "version": "1.0.0", 
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


if __name__ == "__main__":
    uvicorn.run("main:app", port=4000, reload=True)