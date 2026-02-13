# app/middleware/rate_limit.py
"""
Rate Limiting Middleware
Token bucket algorithm with Redis backend
"""

from fastapi import Request, HTTPException, status
from app.database import redis_manager
from app.logging_config import logger
from datetime import datetime
import json
from typing import Optional

class RateLimiter:
    """
    Rate limiter using token bucket algorithm with Redis
    
    Supports:
    - Per-user rate limiting
    - Per-IP rate limiting
    - Tier-based limits (free, pro, enterprise)
    - Multiple time windows (per minute, hour, day)
    """
    
    def __init__(self):
        self.tiers = {
            "free": {
                "requests_per_minute": 10,
                "requests_per_hour": 100,
                "requests_per_day": 1000,
                "tokens_per_day": 100000,
            },
            "pro": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "requests_per_day": 10000,
                "tokens_per_day": 1000000,
            },
            "enterprise": {
                "requests_per_minute": 300,
                "requests_per_hour": 10000,
                "requests_per_day": 100000,
                "tokens_per_day": 10000000,
            }
        }
    
    async def check_rate_limit(
        self,
        user_id: str,
        tier: str,
        endpoint: Optional[str] = None
    ) -> dict:
        """
        Check if user is within rate limits
        
        Returns:
            dict with rate limit info and remaining quota
        
        Raises:
            HTTPException if rate limit exceeded
        """
        if not redis_manager.redis:
            logger.warning("Redis not available, skipping rate limit")
            return {"allowed": True}
        
        limits = self.tiers.get(tier, self.tiers["free"])
        now = datetime.utcnow()
        
        # Check minute limit
        minute_key = f"rate_limit:{user_id}:minute:{now.strftime('%Y%m%d%H%M')}"
        minute_count = await self._check_limit(
            minute_key,
            limits["requests_per_minute"],
            60
        )
        
        # Check hour limit
        hour_key = f"rate_limit:{user_id}:hour:{now.strftime('%Y%m%d%H')}"
        hour_count = await self._check_limit(
            hour_key,
            limits["requests_per_hour"],
            3600
        )
        
        # Check day limit
        day_key = f"rate_limit:{user_id}:day:{now.strftime('%Y%m%d')}"
        day_count = await self._check_limit(
            day_key,
            limits["requests_per_day"],
            86400
        )
        
        return {
            "allowed": True,
            "tier": tier,
            "limits": {
                "minute": {"limit": limits["requests_per_minute"], "remaining": limits["requests_per_minute"] - minute_count},
                "hour": {"limit": limits["requests_per_hour"], "remaining": limits["requests_per_hour"] - hour_count},
                "day": {"limit": limits["requests_per_day"], "remaining": limits["requests_per_day"] - day_count},
            }
        }
    
    async def _check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> int:
        """
        Check specific rate limit window
        
        Raises:
            HTTPException if limit exceeded
        """
        redis = redis_manager.redis
        
        # Get current count
        count = await redis.get(key)
        
        if count is None:
            # First request in this window
            await redis.set(key, 1, ex=window_seconds)
            return 1
        else:
            count = int(count)
            
            if count >= limit:
                # Rate limit exceeded
                ttl = await redis.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "retry_after": ttl
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(ttl),
                        "Retry-After": str(ttl)
                    }
                )
            
            # Increment counter
            new_count = await redis.incr(key)
            return new_count
    
    async def check_token_usage(
        self,
        user_id: str,
        tier: str,
        tokens_requested: int
    ) -> bool:
        """
        Check if user has enough token quota remaining
        
        Returns:
            True if allowed, raises HTTPException if exceeded
        """
        if not redis_manager.redis:
            return True
        
        limits = self.tiers.get(tier, self.tiers["free"])
        now = datetime.utcnow()
        
        # Check daily token usage
        day_key = f"token_usage:{user_id}:day:{now.strftime('%Y%m%d')}"
        redis = redis_manager.redis
        
        current_usage = await redis.get(day_key)
        current_usage = int(current_usage) if current_usage else 0
        
        if current_usage + tokens_requested > limits["tokens_per_day"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Daily token limit exceeded",
                    "limit": limits["tokens_per_day"],
                    "used": current_usage,
                    "requested": tokens_requested
                }
            )
        
        # Increment token usage
        await redis.incrby(day_key, tokens_requested)
        await redis.expire(day_key, 86400)
        
        return True
    
    async def record_token_usage(
        self,
        user_id: str,
        tokens_used: int
    ):
        """Record actual token usage after request completion"""
        if not redis_manager.redis:
            return
        
        now = datetime.utcnow()
        day_key = f"token_usage:{user_id}:day:{now.strftime('%Y%m%d')}"
        
        await redis_manager.redis.incrby(day_key, tokens_used)
        await redis_manager.redis.expire(day_key, 86400)

# Global instance
rate_limiter = RateLimiter()

# ==================== MIDDLEWARE ====================

async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware to apply rate limiting to all requests
    """
    # Skip rate limiting for health checks and metrics
    if request.url.path in ["/health", "/metrics", "/api/v1/health"]:
        return await call_next(request)
    
    # Get user from request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    
    if user:
        try:
            # Check rate limits
            rate_info = await rate_limiter.check_rate_limit(
                user_id=user.id,
                tier=user.tier,
                endpoint=request.url.path
            )
            
            # Add rate limit headers to response
            response = await call_next(request)
            
            # Add rate limit info to headers
            if rate_info.get("limits"):
                minute_info = rate_info["limits"]["minute"]
                response.headers["X-RateLimit-Limit-Minute"] = str(minute_info["limit"])
                response.headers["X-RateLimit-Remaining-Minute"] = str(minute_info["remaining"])
            
            return response
            
        except HTTPException as e:
            # Rate limit exceeded - return 429 response
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content=e.detail,
                headers=e.headers or {}
            )
    else:
        # No user - apply IP-based rate limiting
        client_ip = request.client.host if request.client else "unknown"
        
        try:
            # Simple IP rate limiting (stricter than authenticated)
            minute_key = f"rate_limit:ip:{client_ip}:minute:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
            await rate_limiter._check_limit(minute_key, 5, 60)
            
            return await call_next(request)
            
        except HTTPException as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content={"error": "Rate limit exceeded. Please authenticate for higher limits."},
                headers=e.headers or {}
            )

# ==================== COST TRACKING ====================

class CostTracker:
    """Track costs per user and conversation"""
    
    # Pricing per 1M tokens (approximate, update with actual pricing)
    PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "deepseek-chat": {"input": 0.1, "output": 0.2},
    }
    
    @classmethod
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost in USD for token usage"""
        pricing = cls.PRICING.get(model, {"input": 1.0, "output": 2.0})
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    @classmethod
    async def record_cost(
        cls,
        user_id: str,
        conversation_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ):
        """Record cost to database"""
        from app.database import get_db_context
        from app.models.database import Usage
        from datetime import datetime
        
        cost = cls.calculate_cost(model, input_tokens, output_tokens)
        
        async with get_db_context() as db:
            # Record in usage table
            usage = Usage(
                user_id=user_id,
                date=datetime.utcnow(),
                requests_count=1,
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                tokens_used=input_tokens + output_tokens,
                cost=cost,
                provider_breakdown={model: input_tokens + output_tokens}
            )
            db.add(usage)
            await db.commit()

cost_tracker = CostTracker()
