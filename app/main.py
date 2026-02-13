from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1 import chat, health, chat_streaming
from app.config import settings
from app.logging_config import setup_logging
from app.exceptions import global_exception_handler
from app.services.mcp_orchestrator import mcp_orchestrator
from app.database import init_db, close_db, redis_manager
from app.middleware.monitoring import monitoring_middleware, metrics_router
from app.middleware.rate_limit import rate_limit_middleware
from app.logging_config import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} version {settings.VERSION}")
    
    # Init Database
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize Database: {e}")
        
    # Init Redis
    try:
        await redis_manager.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
    
    # Init MCP
    try:
        await mcp_orchestrator.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize MCP Orchestrator: {e}")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    await mcp_orchestrator.shutdown()
    await redis_manager.disconnect()
    await close_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Should be restricted in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.middleware("http")(monitoring_middleware)
app.middleware("http")(rate_limit_middleware)

# Exception handlers
app.add_exception_handler(Exception, global_exception_handler)

# Include routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(chat_streaming.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(metrics_router)

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
