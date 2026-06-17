import asyncio
import os
import sys
import logging
from pydantic import BaseModel

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nitrostack import DIContainer, injectable, ConfigModule, ConfigService, ExecutionContext
from nitrostack.core.errors import DependencyResolutionError, ConfigurationError
from nitrostack.core.context import FileLogger

@injectable(deps=["MissingDependency"])
class FaultyController:
    def __init__(self, missing):
        self.missing = missing

def test_custom_di_exceptions():
    print("Testing custom DI resolution exceptions...")
    container = DIContainer.get_instance()
    container.register(FaultyController)
    
    # Try resolving FaultyController; should raise DependencyResolutionError
    try:
        container.resolve(FaultyController)
        assert False, "Should have raised DependencyResolutionError"
    except DependencyResolutionError as e:
        print("Success! Raised expected DependencyResolutionError:", e)
        assert "MissingDependency" in str(e)

def test_custom_config_exceptions():
    print("\nTesting custom config validation exceptions...")
    # Clean container
    DIContainer.reset()
    
    # Create validation function that fails
    validator = lambda cfg: False
    
    try:
        ConfigModule.for_root(
            ignore_env_file=True,
            validate=validator
        )
        assert False, "Should have raised ConfigurationError"
    except ConfigurationError as e:
        print("Success! Raised expected ConfigurationError:", e)
        assert "Configuration validation failed" in str(e)

def test_file_logger_customizations():
    print("\nTesting FileLogger customization options...")
    
    # Test 1: Test Log Level environment setting
    os.environ["NITROSTACK_LOG_LEVEL"] = "WARNING"
    logger_warn = FileLogger(log_file="test_warn.log", name="test_warn")
    assert logger_warn.logger.level == logging.WARNING
    print("Success! Logger correctly configured with level WARNING.")
    
    # Clean up handlers and file if created
    for h in list(logger_warn.logger.handlers):
        h.close()
        logger_warn.logger.removeHandler(h)
    if os.path.exists("test_warn.log"):
        os.remove("test_warn.log")
        
    # Test 2: Test Log File path environment setting
    os.environ["NITROSTACK_LOG_LEVEL"] = "DEBUG"
    os.environ["NITROSTACK_LOG_FILE"] = "test_custom_file.log"
    logger_file = FileLogger(name="test_file")
    
    # Check if a file handler is registered with the correct file path
    file_handlers = [h for h in logger_file.logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) >= 1
    assert "test_custom_file.log" in file_handlers[0].baseFilename
    print("Success! Logger correctly configured output to custom file:", file_handlers[0].baseFilename)
    
    # Clean up handlers and file
    for h in list(logger_file.logger.handlers):
        h.close()
        logger_file.logger.removeHandler(h)
    if os.path.exists("test_custom_file.log"):
        os.remove("test_custom_file.log")

if __name__ == "__main__":
    test_custom_di_exceptions()
    test_custom_config_exceptions()
    test_file_logger_customizations()
    print("\nAll production readiness tests passed successfully!")
