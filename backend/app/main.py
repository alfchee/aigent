from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.core.agent import NaviBot
from app.skills.scheduler import start_scheduler
import asyncio

app = FastAPI(title="NaviBot API", version="0.1.0")

# Initialize Agent
bot = NaviBot()

# Start Scheduler on startup
@app.on_event("startup")
async def startup_event():
    start_scheduler()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@app.get("/")
async def root():
    return {"message": "NaviBot Backend is running", "status": "ok"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response_text = await bot.send_message(request.message)
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8231, reload=True)
