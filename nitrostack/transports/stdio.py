import sys
import contextlib
from typing import Generator

class SafeStdoutWrapper:
    """
    Wrapper for sys.stdout that redirects all text writes to sys.stderr,
    but preserves sys.stdout.buffer for binary JSON-RPC transport frames.
    """
    def __init__(self, original_stdout):
        self._original = original_stdout
        # Keep original binary buffer intact for MCP JSON-RPC transport
        self.buffer = original_stdout.buffer

    def write(self, data: str) -> int:
        sys.stderr.write(data)
        sys.stderr.flush()
        return len(data)

    def flush(self) -> None:
        sys.stderr.flush()

    def __getattr__(self, name: str):
        return getattr(self._original, name)

@contextlib.contextmanager
def safe_stdio_transport() -> Generator[None, None, None]:
    """Context manager that safely wraps sys.stdout during stdio transport execution."""
    original_stdout = sys.stdout
    sys.stdout = SafeStdoutWrapper(original_stdout)
    try:
        yield
    finally:
        sys.stdout = original_stdout
