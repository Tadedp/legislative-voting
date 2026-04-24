import logging
import logging.config
import sys

import structlog
from structlog.types import EventDict, WrappedLogger, Processor

_MASKED_KEYS: frozenset[str] = frozenset(
    {
        "password",
    }
)

_MASK_VALUE = "***REDACTED***"

def _mask_sensitive_fields(
    logger: WrappedLogger, 
    method: str, 
    event_dict: EventDict,
) -> EventDict:
    for key in list(event_dict.keys()):
        if key.lower() in _MASKED_KEYS:
            event_dict[key] = _MASK_VALUE    
    
    return event_dict

def _add_service_name(service_name: str):
    def processor(
        logger: WrappedLogger, 
        method: str, 
        event_dict: EventDict,
    ) -> EventDict:
        event_dict["service"] = service_name
        return event_dict

    return processor

def configure_logging(
    log_level: str, 
    service_name: str
) -> None:
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        _add_service_name(service_name),
        _mask_sensitive_fields,
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.dict_tracebacks,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": shared_processors,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.EventRenamer(to="message"),
                    structlog.processors.JSONRenderer(),
                ],
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "json",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": log_level,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    })