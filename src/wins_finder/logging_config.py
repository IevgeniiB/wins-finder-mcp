"""Logging configuration using structlog."""

import structlog
import logging
import sys
from typing import Any


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    enable_colors: bool = False
) -> None:
    """Configure beautiful structured logging with structlog.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_type: Output format ('json' or 'console')  
        enable_colors: Enable colored output for console format
    """
    
    # Base processors that are always used
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Choose final renderer based on format type
    if format_type == "console":
        if enable_colors:
            processors.append(
                structlog.dev.ConsoleRenderer(colors=True)
            )
        else:
            processors.append(
                structlog.dev.ConsoleRenderer(colors=False)
            )
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set standard library logging level - use stderr for MCP compatibility
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper())
    )


def get_logger(name: str = None, **initial_context: Any) -> structlog.BoundLogger:
    """Get a configured structlog logger.
    
    Args:
        name: Logger name (defaults to calling module)
        **initial_context: Initial context to bind to logger
        
    Returns:
        Configured structlog logger with initial context
    """
    if name:
        logger = structlog.get_logger(name)
    else:
        logger = structlog.get_logger()
    
    if initial_context:
        logger = logger.bind(**initial_context)
    
    return logger