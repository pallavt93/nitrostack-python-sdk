import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Protocol, List, Dict, Optional

# Protocol for Logger matching TS Winstron logger equivalent (Section 13)
class Logger(Protocol):
    def debug(self, message: str, meta: dict | None = None) -> None: ...
    def info(self, message: str, meta: dict | None = None) -> None: ...
    def warn(self, message: str, meta: dict | None = None) -> None: ...
    def error(self, message: str, meta: dict | None = None) -> None: ...

class FileLogger:
    """
    Logger implementation that writes to a file or stdout/stderr based on transport settings.
    This prevents corrupting the MCP stdio JSON-RPC transport.
    """
    def __init__(self, log_file: Optional[str] = None, name: str = "nitrostack"):
        self.logger = logging.getLogger(name)
        
        # Read log level from environment
        level_str = os.environ.get("NITROSTACK_LOG_LEVEL", "DEBUG").upper()
        level = getattr(logging, level_str, logging.DEBUG)
        self.logger.setLevel(level)
        
        # Avoid adding duplicate handlers if initialized multiple times
        if not self.logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] (%(name)s): %(message)s'
            )
            
            # Check if stdout logging is explicitly requested or safe (e.g. HTTP transport)
            log_to_stdout = (
                os.environ.get("NITROSTACK_LOG_TO_STDOUT", "false").lower() == "true"
                or os.environ.get("MCP_TRANSPORT_TYPE") == "http"
            )
            
            if log_to_stdout:
                sh = logging.StreamHandler(sys.stdout)
                sh.setLevel(level)
                sh.setFormatter(formatter)
                self.logger.addHandler(sh)
            else:
                # Determine log file path
                target_file = log_file or os.environ.get("NITROSTACK_LOG_FILE", "nitrostack.log")
                try:
                    fh = logging.FileHandler(target_file, encoding='utf-8')
                    fh.setLevel(level)
                    fh.setFormatter(formatter)
                    self.logger.addHandler(fh)
                except Exception:
                    # Fallback to sys.stderr to avoid stdout pollution in stdio transport
                    sh = logging.StreamHandler(sys.stderr)
                    sh.setLevel(level)
                    sh.setFormatter(formatter)
                    self.logger.addHandler(sh)
                
    def _format_message(self, message: str, meta: dict | None = None) -> str:
        if meta:
            return f"{message} | meta: {meta}"
        return message

    def debug(self, message: str, meta: dict | None = None) -> None:
        self.logger.debug(self._format_message(message, meta))

    def info(self, message: str, meta: dict | None = None) -> None:
        self.logger.info(self._format_message(message, meta))

    def warn(self, message: str, meta: dict | None = None) -> None:
        self.logger.warning(self._format_message(message, meta))

    def error(self, message: str, meta: dict | None = None) -> None:
        self.logger.error(self._format_message(message, meta))

@dataclass
class AuthContext:
    subject: str | None = None       # user/client identifier
    scopes: List[str] = field(default_factory=list)  # granted permissions
    client_id: str | None = None     # machine-to-machine
    exp: int | None = None           # expiration timestamp
    iat: int | None = None           # issued-at timestamp
    iss: str | None = None           # issuer URL
    claims: Dict[str, Any] = field(default_factory=dict)  # custom claims
    token_payload: Any = None        # full decoded token

class TaskCancelledError(Exception):
    """Raised when an MCP background task has been cancelled."""
    pass

class TaskContext:
    """Context representation for long-running asynchronous MCP tasks."""
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.progress_message: str = ""
        self.is_cancelled: bool = False

    def update_progress(self, message: str) -> None:
        self.progress_message = message
        try:
            from nitrostack.core.task import TaskRegistry
            TaskRegistry.update_progress(self.task_id, message)
        except Exception:
            pass

    def cancel(self) -> None:
        self.is_cancelled = True
        try:
            from nitrostack.core.task import TaskRegistry
            TaskRegistry.cancel_task(self.task_id)
        except Exception:
            pass

    def throw_if_cancelled(self) -> None:
        try:
            from nitrostack.core.task import TaskRegistry
            if TaskRegistry.is_task_cancelled(self.task_id):
                self.is_cancelled = True
        except Exception:
            pass
        if self.is_cancelled:
            raise TaskCancelledError(f"Task {self.task_id} has been cancelled.")

@dataclass
class ExecutionContext:
    request_id: str
    tool_name: str | None = None
    logger: Logger = field(default_factory=lambda: FileLogger())
    metadata: dict = field(default_factory=dict)
    auth: AuthContext | None = None
    task: TaskContext | None = None
