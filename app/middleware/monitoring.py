# app/middleware/monitoring.py
"""
Monitoring and Observability Middleware
Prometheus metrics, structured logging, and distributed tracing
"""

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from app.logging_config import logger
import time
import json
from typing import Callable
from datetime import datetime
import uuid

# ==================== PROMETHEUS METRICS ====================

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

http_request_size_bytes = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint']
)

http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint']
)

# Application Metrics
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

active_conversations = Gauge(
    'active_conversations',
    'Number of active conversations'
)

llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['provider', 'model', 'status']
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['provider', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'model', 'type']  # type: input, output
)

llm_cost_total = Counter(
    'llm_cost_total',
    'Total LLM cost in USD',
    ['provider', 'model']
)

# MCP Metrics
mcp_tool_calls_total = Counter(
    'mcp_tool_calls_total',
    'Total MCP tool calls',
    ['tool_name', 'server_name', 'status']
)

mcp_tool_duration_seconds = Histogram(
    'mcp_tool_duration_seconds',
    'MCP tool execution duration',
    ['tool_name', 'server_name'],
    buckets=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0]
)

# Database Metrics
db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table', 'status']
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table']
)

# Cache Metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type']
)

# Error Metrics
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'endpoint']
)

# User Metrics
users_active = Gauge(
    'users_active',
    'Number of active users'
)

# System Info
system_info = Info(
    'system',
    'System information'
)

# ==================== MIDDLEWARE ====================

async def monitoring_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware to collect metrics for each request
    """
    # Generate request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Start timing
    start_time = time.time()
    
    # Increment active connections
    active_connections.inc()
    
    # Get request size
    request_size = len(await request.body()) if request.method in ["POST", "PUT", "PATCH"] else 0
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        endpoint = request.url.path
        method = request.method
        status_code = response.status_code
        
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        if request_size:
            http_request_size_bytes.labels(
                method=method,
                endpoint=endpoint
            ).observe(request_size)
        
        # Log request
        log_request(
            request=request,
            response=response,
            duration=duration,
            request_id=request_id
        )
        
        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.4f}s"
        
        return response
        
    except Exception as e:
        # Record error
        duration = time.time() - start_time
        
        errors_total.labels(
            error_type=type(e).__name__,
            endpoint=request.url.path
        ).inc()
        
        # Log error
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration": duration,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        
        raise
        
    finally:
        # Decrement active connections
        active_connections.dec()

def log_request(
    request: Request,
    response: Response,
    duration: float,
    request_id: str
):
    """
    Structured logging for requests
    """
    user_id = None
    if hasattr(request.state, "user"):
        user_id = request.state.user.id
    
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration": f"{duration:.4f}s",
        "user_id": user_id,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    
    # Log at appropriate level
    if response.status_code >= 500:
        logger.error("Request failed", extra=log_data)
    elif response.status_code >= 400:
        logger.warning("Request error", extra=log_data)
    else:
        logger.info("Request completed", extra=log_data)

# ==================== METRICS ENDPOINT ====================

from fastapi import APIRouter

metrics_router = APIRouter()

@metrics_router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ==================== DISTRIBUTED TRACING ====================

class TracingContext:
    """Context for distributed tracing"""
    
    def __init__(self, trace_id: str = None, span_id: str = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.parent_span_id = None
        self.spans = []
    
    def create_span(self, name: str, **attributes):
        """Create a new span"""
        span = {
            "span_id": str(uuid.uuid4()),
            "parent_span_id": self.span_id,
            "name": name,
            "start_time": datetime.utcnow().isoformat(),
            "attributes": attributes
        }
        self.spans.append(span)
        return span
    
    def end_span(self, span: dict):
        """End a span"""
        span["end_time"] = datetime.utcnow().isoformat()
        span["duration"] = (
            datetime.fromisoformat(span["end_time"]) -
            datetime.fromisoformat(span["start_time"])
        ).total_seconds()

# ==================== HEALTH CHECKS ====================

from fastapi.responses import JSONResponse

@metrics_router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "checks": {}
    }
    
    # Check database
    try:
        from app.database import get_db_context
        async with get_db_context() as db:
            await db.execute("SELECT 1")
        health_status["checks"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check Redis
    try:
        from app.database import redis_manager
        if redis_manager.redis:
            await redis_manager.redis.ping()
            health_status["checks"]["redis"] = {"status": "healthy"}
        else:
            health_status["checks"]["redis"] = {"status": "not_connected"}
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Check MCP servers
    try:
        from app.services.mcp_orchestrator import mcp_orchestrator
        mcp_health = await mcp_orchestrator.check_health()
        connected_servers = sum(1 for status in mcp_health.values() if status == "connected")
        health_status["checks"]["mcp"] = {
            "status": "healthy" if connected_servers > 0 else "degraded",
            "connected_servers": connected_servers,
            "servers": mcp_health
        }
    except Exception as e:
        health_status["checks"]["mcp"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Set HTTP status code
    status_code = 200
    if health_status["status"] == "unhealthy":
        status_code = 503
    elif health_status["status"] == "degraded":
        status_code = 200  # Still operational
    
    return JSONResponse(
        content=health_status,
        status_code=status_code
    )

@metrics_router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes readiness probe
    Returns 200 if service is ready to accept traffic
    """
    # Check critical dependencies
    try:
        from app.database import get_db_context
        async with get_db_context() as db:
            await db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse(
            content={"status": "not_ready", "error": str(e)},
            status_code=503
        )

@metrics_router.get("/health/live")
async def liveness_check():
    """
    Kubernetes liveness probe
    Returns 200 if service is alive
    """
    return {"status": "alive"}
