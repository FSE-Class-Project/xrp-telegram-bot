"""
Monitoring, logging, and observability utilities
"""
import time
import logging
import json
from functools import wraps
from typing import Any, Dict, Optional
from datetime import datetime
import traceback

# Try to import Sentry for error tracking
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

# Configure structured logging
class StructuredLogger:
    """Structured logging for better observability"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create console handler with JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(self.JsonFormatter())
        self.logger.addHandler(handler)
    
    class JsonFormatter(logging.Formatter):
        """JSON log formatter"""
        
        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = traceback.format_exception(*record.exc_info)
            
            # Add extra fields
            if hasattr(record, "extra_fields"):
                log_data.update(record.extra_fields)
            
            return json.dumps(log_data)
    
    def log(self, level: str, message: str, **kwargs):
        """Log with extra fields"""
        extra = {"extra_fields": kwargs}
        getattr(self.logger, level.lower())(message, extra=extra)
    
    def info(self, message: str, **kwargs):
        self.log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log("error", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self.log("debug", message, **kwargs)

# Create default logger
logger = StructuredLogger(__name__)

# Metrics collection
class MetricsCollector:
    """Collect and track application metrics"""
    
    def __init__(self):
        self.metrics = {
            "requests": {},
            "transactions": {},
            "errors": {},
            "performance": {}
        }
    
    def record_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """Record API request metrics"""
        key = f"{method}_{endpoint}"
        if key not in self.metrics["requests"]:
            self.metrics["requests"][key] = {
                "count": 0,
                "total_duration": 0,
                "status_codes": {}
            }
        
        self.metrics["requests"][key]["count"] += 1
        self.metrics["requests"][key]["total_duration"] += duration
        
        status_key = str(status_code)
        if status_key not in self.metrics["requests"][key]["status_codes"]:
            self.metrics["requests"][key]["status_codes"][status_key] = 0
        self.metrics["requests"][key]["status_codes"][status_key] += 1
    
    def record_transaction(self, amount: float, success: bool, duration: float):
        """Record XRP transaction metrics"""
        date_key = datetime.utcnow().strftime("%Y-%m-%d")
        
        if date_key not in self.metrics["transactions"]:
            self.metrics["transactions"][date_key] = {
                "count": 0,
                "success": 0,
                "failed": 0,
                "total_amount": 0,
                "total_duration": 0
            }
        
        self.metrics["transactions"][date_key]["count"] += 1
        if success:
            self.metrics["transactions"][date_key]["success"] += 1
        else:
            self.metrics["transactions"][date_key]["failed"] += 1
        self.metrics["transactions"][date_key]["total_amount"] += amount
        self.metrics["transactions"][date_key]["total_duration"] += duration
    
    def record_error(self, error_type: str, endpoint: Optional[str] = None):
        """Record error metrics"""
        if error_type not in self.metrics["errors"]:
            self.metrics["errors"][error_type] = {
                "count": 0,
                "endpoints": {}
            }
        
        self.metrics["errors"][error_type]["count"] += 1
        
        if endpoint:
            if endpoint not in self.metrics["errors"][error_type]["endpoints"]:
                self.metrics["errors"][error_type]["endpoints"][endpoint] = 0
            self.metrics["errors"][error_type]["endpoints"][endpoint] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": self.metrics
        }
    
    def reset_metrics(self):
        """Reset metrics (useful for periodic reporting)"""
        self.metrics = {
            "requests": {},
            "transactions": {},
            "errors": {},
            "performance": {}
        }

# Global metrics collector
metrics = MetricsCollector()

# Performance monitoring decorator
def monitor_performance(operation_name: str):
    """Decorator to monitor function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"Operation completed: {operation_name}",
                    operation=operation_name,
                    duration=duration,
                    success=True
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    f"Operation failed: {operation_name}",
                    operation=operation_name,
                    duration=duration,
                    success=False,
                    error=str(e)
                )
                
                metrics.record_error(type(e).__name__, operation_name)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"Operation completed: {operation_name}",
                    operation=operation_name,
                    duration=duration,
                    success=True
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    f"Operation failed: {operation_name}",
                    operation=operation_name,
                    duration=duration,
                    success=False,
                    error=str(e)
                )
                
                metrics.record_error(type(e).__name__, operation_name)
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Initialize Sentry for error tracking
def init_sentry(dsn: Optional[str] = None, environment: str = "production"):
    """Initialize Sentry error tracking"""
    if not SENTRY_AVAILABLE:
        logger.warning("Sentry SDK not installed, skipping initialization")
        return
    
    if not dsn:
        logger.warning("No Sentry DSN provided, skipping initialization")
        return
    
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,  # Capture 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # Profile 10% of transactions
            attach_stacktrace=True,
            send_default_pii=False,  # Don't send personally identifiable information
            before_send=filter_sensitive_data,
        )
        
        logger.info("Sentry initialized successfully", environment=environment)
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")

def filter_sensitive_data(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter sensitive data from Sentry events"""
    # Remove sensitive fields
    sensitive_fields = ["password", "secret", "token", "api_key", "private_key", "seed"]
    
    def remove_sensitive(data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: "***REDACTED***" if any(s in k.lower() for s in sensitive_fields) else remove_sensitive(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [remove_sensitive(item) for item in data]
        else:
            return data
    
    # Clean the event
    if "request" in event:
        event["request"] = remove_sensitive(event["request"])
    
    if "extra" in event:
        event["extra"] = remove_sensitive(event["extra"])
    
    if "contexts" in event:
        event["contexts"] = remove_sensitive(event["contexts"])
    
    return event

# Health check utilities
class HealthChecker:
    """System health checking"""
    
    @staticmethod
    async def check_database(db_session) -> Dict[str, Any]:
        """Check database health"""
        try:
            result = db_session.execute("SELECT 1")
            return {"status": "healthy", "response_time": 0}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    @staticmethod
    async def check_xrp_connection() -> Dict[str, Any]:
        """Check XRP Ledger connection"""
        try:
            from backend.services.xrp_service import xrp_service
            # Try to get server info
            response = xrp_service.client.request({
                "command": "server_info"
            })
            if response.is_successful():
                return {"status": "healthy", "network": "testnet"}
            else:
                return {"status": "degraded", "error": "Connection established but unhealthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    @staticmethod
    async def check_telegram_bot() -> Dict[str, Any]:
        """Check Telegram bot status"""
        try:
            import telegram
            from backend.config import settings
            
            bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
            me = await bot.get_me()
            return {
                "status": "healthy",
                "bot_username": me.username,
                "bot_id": me.id
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    @staticmethod
    async def get_full_health_status(db_session) -> Dict[str, Any]:
        """Get comprehensive health status"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": await HealthChecker.check_database(db_session),
                "xrp_ledger": await HealthChecker.check_xrp_connection(),
                "telegram_bot": await HealthChecker.check_telegram_bot(),
            },
            "metrics": metrics.get_metrics()
        }

# Export utilities
__all__ = [
    "logger",
    "metrics",
    "monitor_performance",
    "init_sentry",
    "HealthChecker",
    "MetricsCollector",
    "StructuredLogger"
]