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

from nitrostack import ServerConfig, mcp_app, McpApplicationFactory, module, prompt, PromptMessage, OAuthModule, OAuthService

# Test prompt messages wrapping
@injectable()
class DummyPromptController:
    @prompt(
        name="single_msg_prompt",
        description="Returns a single message"
    )
    async def single_msg(self, args: dict, context: ExecutionContext) -> PromptMessage:
        return PromptMessage(role="user", content="Hello single!")

@module(name="dummy", controllers=[DummyPromptController])
class DummyModule:
    pass

def test_prompt_messages_wrapping():
    print("\nTesting single prompt message wrapping...")
    from nitrostack.testing import NitroTestingModule
    async def run():
        harness = await NitroTestingModule.create(DummyModule)
        res = await harness.get_prompt("single_msg_prompt", {})
        print("DEBUG PROMPT MSG:", res[0])
        print("DEBUG CONTENT TYPE:", type(res[0].content))
        print("DEBUG CONTENT TEXT:", getattr(res[0].content, "text", None))
        assert isinstance(res, list)
        assert len(res) == 1
        assert getattr(res[0].content, "text", None) == "Hello single!"
    asyncio.run(run())
    print("Success! Single prompt message result was wrapped into a list.")

def test_server_config_transport_override():
    print("\nTesting ServerConfig transport_type override...")
    cfg = ServerConfig(name="test", transport_type="http")
    assert cfg.transport_type == "http"
    print("Success! transport_type attribute correctly set in ServerConfig.")

def test_oauth_jwks_configuration():
    print("\nTesting OAuthModule JWKS parameter configuration...")
    os.environ["JWKS_URI"] = "https://example.com/keys"
    os.environ["TOKEN_AUDIENCE"] = "my-audience"
    os.environ["TOKEN_ISSUER"] = "my-issuer"
    
    DIContainer.reset()
    OAuthModule.for_root(
        resource_uri="mcp://test",
        authorization_servers=["https://example.com"],
        scopes_supported=["read"]
    )
    
    svc = DIContainer.get_instance().resolve(OAuthService)
    assert svc.jwks_uri == "https://example.com/keys"
    assert svc.audience == "my-audience"
    assert svc.issuer == "my-issuer"
    print("Success! OAuth jwks_uri, audience, and issuer correctly configured via env variables.")

if __name__ == "__main__":
    test_custom_di_exceptions()
    test_custom_config_exceptions()
    test_file_logger_customizations()
    test_prompt_messages_wrapping()
    test_server_config_transport_override()
    test_oauth_jwks_configuration()
    print("\nAll production readiness tests passed successfully!")
