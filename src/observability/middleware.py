"""Observability middleware: Sentry, Prometheus, structured logging."""

import logging
import os
import uuid
from contextvars import ContextVar
from time import perf_counter

import sentry_sdk
from fastapi import FastAPI, Request, Response
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def setup_observability(app: FastAPI) -> None:
    """Configure Sentry, Prometheus metrics, and structured logging."""

    _setup_sentry(app)
    _setup_prometheus(app)
    _setup_structured_logging()
    app.add_middleware(RequestIdMiddleware)


def _setup_sentry(app: FastAPI) -> None:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return

    environment = os.environ.get("SENTRY_ENVIRONMENT", "development")
    traces_sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0"))

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(app=app, transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )


def _setup_prometheus(app: FastAPI) -> None:
    Instrumentator(
        should_group_status_codes=False,
        should_respect_env_var=True,
        env_var_name="ENABLE_METRICS",
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


def _setup_structured_logging() -> None:
    import structlog

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=open(os.devnull, "w"),
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(),
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to every request and propagates it to Sentry."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)

        sentry_sdk.set_tag("request_id", request_id)
        sentry_sdk.set_context(
            "request",
            {
                "method": request.method,
                "path": request.url.path,
                "query_string": str(request.query_params),
                "request_id": request_id,
            },
        )

        start = perf_counter()
        response = await call_next(request)
        elapsed = perf_counter() - start

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"

        return response


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_var.get()
