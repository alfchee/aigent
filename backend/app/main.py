from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.llm import default_llm
from app.skills.registry import registry
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("navibot")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("NaviBot 2.0 (Phoenix) is starting up...")
    
    # Initialize LLM (optional check)
    try:
        # Check connection or load models
        pass
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")

    yield
    
    # Shutdown logic
    logger.info("NaviBot 2.0 (Phoenix) is shutting down...")

app = FastAPI(
    title="NaviBot 2.0 (Phoenix)",
    description="Agentic Ecosystem Orchestrated by LangGraph",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "Welcome to NaviBot 2.0 (The Phoenix)", "status": "operational"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
