from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1 import chat, health
from app.config import settings
from app.logging_config import setup_logging
from app.exceptions import global_exception_handler
from app.services.mcp_orchestrator import mcp_orchestrator
from app.logging_config import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} version {settings.VERSION}")
    try:
        await mcp_orchestrator.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize MCP Orchestrator: {e}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    await mcp_orchestrator.shutdown()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Exception handlers
app.add_exception_handler(Exception, global_exception_handler)

# Include versioned routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
