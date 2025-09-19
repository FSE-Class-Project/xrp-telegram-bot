"""Monitoring, logging, and observability utilities."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, TypeVar

# Try to import Sentry for error tracking (optional)
SENTRY_AVAILABLE = False
sentry_sdk = None
FastApiIntegration = None
SqlalchemyIntegration = None

try:
    import sentry_sdk as _sentry_sdk  # type: ignore
    from sentry_sdk.integrations.fastapi import (  # type: ignore
        FastApiIntegration as _FastApiIntegration,
    )
    from sentry_sdk.integrations.sqlalchemy import (  # type: ignore
        SqlalchemyIntegration as _SqlalchemyIntegration,
    )

    sentry_sdk = _sentry_sdk
    FastApiIntegration = _FastApiIntegration
    SqlalchemyIntegration = _SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    pass  # Sentry is optional

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


# Configure structured logging
class StructuredLogger:
    """Structured logging for better observability."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        # Only add handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(self.JsonFormatter())
            self.logger.addHandler(handler)

    class JsonFormatter(logging.Formatter):
        """JSON log formatter."""

        def format(self, record: logging.LogRecord) -> str:
            log_data: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
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

            # Safely check for extra fields
            # Use getattr with default to avoid attribute errors
            extra_fields = getattr(record, "extra_fields", None)
            if extra_fields:
                log_data.update(extra_fields)

            return json.dumps(log_data)

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log with extra fields."""
        log_level = getattr(logging, level.upper(), logging.INFO)
        if kwargs:
            # Create a LogAdapter or use extra parameter properly
            self.logger.log(log_level, message, extra={"extra_fields": kwargs})
        else:
            self.logger.log(log_level, message)

    def info(self, message: str, **kwargs: Any) -> None:
        self.log("info", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log("warning", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log("error", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self.log("debug", message, **kwargs)


# Create default logger
logger = StructuredLogger(__name__)


# Metrics collection
class MetricsCollector:
    """Collect and track application metrics."""

    def __init__(self):
        self.metrics: dict[str, dict[str, Any]] = {
            "requests": {},
            "transactions": {},
            "errors": {},
            "performance": {},
        }

    def record_request(self, endpoint: str, method: str, status_code: int, duration: float) -> None:
        """Record API request metrics."""
        key = f"{method}_{endpoint}"
        if key not in self.metrics["requests"]:
            self.metrics["requests"][key] = {
                "count": 0,
                "total_duration": 0,
                "status_codes": {},
            }

        self.metrics["requests"][key]["count"] += 1
        self.metrics["requests"][key]["total_duration"] += duration

        status_key = str(status_code)
        if status_key not in self.metrics["requests"][key]["status_codes"]:
            self.metrics["requests"][key]["status_codes"][status_key] = 0
        self.metrics["requests"][key]["status_codes"][status_key] += 1

    def record_transaction(self, amount: float, success: bool, duration: float) -> None:
        """Record XRP transaction metrics."""
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if date_key not in self.metrics["transactions"]:
            self.metrics["transactions"][date_key] = {
                "count": 0,
                "success": 0,
                "failed": 0,
                "total_amount": 0,
                "total_duration": 0,
            }

        self.metrics["transactions"][date_key]["count"] += 1
        if success:
            self.metrics["transactions"][date_key]["success"] += 1
        else:
            self.metrics["transactions"][date_key]["failed"] += 1
        self.metrics["transactions"][date_key]["total_amount"] += amount
        self.metrics["transactions"][date_key]["total_duration"] += duration

    def record_error(self, error_type: str, endpoint: str | None = None) -> None:
        """Record error metrics."""
        if error_type not in self.metrics["errors"]:
            self.metrics["errors"][error_type] = {"count": 0, "endpoints": {}}

        self.metrics["errors"][error_type]["count"] += 1

        if endpoint:
            if endpoint not in self.metrics["errors"][error_type]["endpoints"]:
                self.metrics["errors"][error_type]["endpoints"][endpoint] = 0
            self.metrics["errors"][error_type]["endpoints"][endpoint] += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": self.metrics,
        }

    def reset_metrics(self) -> None:
        """Reset metrics (useful for periodic reporting)."""
        self.metrics = {
            "requests": {},
            "transactions": {},
            "errors": {},
            "performance": {},
        }


# Global metrics collector
metrics = MetricsCollector()


# Performance monitoring decorator
def monitor_performance(operation_name: str) -> Callable[[F], F]:
    """Monitor function performance."""

    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time

                    logger.info(
                        f"Operation completed: {operation_name}",
                        operation=operation_name,
                        duration=duration,
                        success=True,
                    )

                    return result
                except Exception as e:
                    duration = time.time() - start_time

                    logger.error(
                        f"Operation failed: {operation_name}",
                        operation=operation_name,
                        duration=duration,
                        success=False,
                        error=str(e),
                    )

                    metrics.record_error(type(e).__name__, operation_name)
                    raise

            return async_wrapper  # type: ignore
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    logger.info(
                        f"Operation completed: {operation_name}",
                        operation=operation_name,
                        duration=duration,
                        success=True,
                    )

                    return result
                except Exception as e:
                    duration = time.time() - start_time

                    logger.error(
                        f"Operation failed: {operation_name}",
                        operation=operation_name,
                        duration=duration,
                        success=False,
                        error=str(e),
                    )

                    metrics.record_error(type(e).__name__, operation_name)
                    raise

            return sync_wrapper  # type: ignore

    return decorator


def filter_sensitive_data(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:  # noqa: ARG001
    """Filter sensitive data from Sentry events."""
    # Remove sensitive fields
    sensitive_fields = [
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
        "seed",
    ]

    def remove_sensitive(data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: (
                    "***REDACTED***"
                    if any(s in k.lower() for s in sensitive_fields)
                    else remove_sensitive(v)
                )
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


# Initialize Sentry for error tracking
def init_sentry(dsn: str | None = None, environment: str = "production") -> None:
    """Initialize Sentry error tracking."""
    if not SENTRY_AVAILABLE or sentry_sdk is None:
        logger.warning("Sentry SDK not installed, skipping initialization")
        return

    if not dsn:
        logger.warning("No Sentry DSN provided, skipping initialization")
        return

    try:
        integrations: list[Any] = []
        if FastApiIntegration is not None:
            integrations.append(FastApiIntegration(transaction_style="endpoint"))
        if SqlalchemyIntegration is not None:
            integrations.append(SqlalchemyIntegration())

        # Initialize with proper type handling
        init_params: dict[str, Any] = {
            "dsn": dsn,
            "environment": environment,
            "integrations": integrations,
            "traces_sample_rate": 0.1,
            "profiles_sample_rate": 0.1,
            "attach_stacktrace": True,
            "send_default_pii": False,
            "before_send": filter_sensitive_data,
        }

        sentry_sdk.init(**init_params)

        logger.info("Sentry initialized successfully", environment=environment)
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")


# Health check utilities
class HealthChecker:
    """System health checking."""

    @staticmethod
    async def check_database(db_session: Any) -> dict[str, Any]:
        """Check database health."""
        try:
            # Import inside function to avoid circular imports
            from sqlalchemy import text

            # Simple health check query
            start_time = time.time()
            db_session.execute(text("SELECT 1"))
            response_time = time.time() - start_time

            return {"status": "healthy", "response_time": response_time}
        except ImportError:
            return {
                "status": "unhealthy",
                "error": "SQLAlchemy not properly installed",
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_xrp_connection() -> dict[str, Any]:
        """Check XRP Ledger connection."""
        try:
            # Import inside function to avoid circular imports
            from xrpl.models.requests import ServerInfo

            from backend.services.xrp_service import xrp_service

            # Simple server_info request
            start_time = time.time()
            # Instantiate the ServerInfo model instead of using a dict
            response = xrp_service.client.request(ServerInfo())
            response_time = time.time() - start_time

            if response.is_successful():
                return {
                    "status": "healthy",
                    "network": "testnet",  # might want to get this from the response itself
                    "response_time": response_time,
                }
            else:
                return {
                    "status": "degraded",
                    "error": "Connection established but unhealthy",
                    "details": response.result.get("error_message") or response.result,
                }
        except ImportError as e:
            return {
                "status": "unhealthy",
                "error": f"XRP service not available: {str(e)}",
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_telegram_bot() -> dict[str, Any]:
        """Check Telegram bot status."""
        try:
            # Import config inside function
            from backend.config import settings

            # Check if token is configured
            if hasattr(settings, "TELEGRAM_BOT_TOKEN") and settings.TELEGRAM_BOT_TOKEN:
                return {
                    "status": "configured",
                    "message": "Bot token configured",
                    "token_length": len(settings.TELEGRAM_BOT_TOKEN),
                }
            else:
                return {
                    "status": "not_configured",
                    "error": "TELEGRAM_BOT_TOKEN not set",
                }
        except ImportError:
            return {
                "status": "error",
                "error": "Backend configuration not available",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    async def get_full_health_status(db_session: Any) -> dict[str, Any]:
        """Get comprehensive health status."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "database": await HealthChecker.check_database(db_session),
                "xrp_ledger": await HealthChecker.check_xrp_connection(),
                "telegram_bot": await HealthChecker.check_telegram_bot(),
            },
            "metrics": metrics.get_metrics(),
        }


# Export utilities
__all__ = [
    "logger",
    "metrics",
    "monitor_performance",
    "init_sentry",
    "HealthChecker",
    "MetricsCollector",
    "StructuredLogger",
    "SENTRY_AVAILABLE",
]
