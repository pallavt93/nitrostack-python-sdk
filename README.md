# NitroStack Python SDK

A Python-idiomatic port of the **NitroStack** Model Context Protocol (MCP) framework, enabling NestJS-like modular architecture, dependency injection, execution pipelines, background task processing, built-in authentication modules, and a diagnostic testing harness.

---

## Features

- **Nested Modular Architecture**: Group components cleanly with `@module`.
- **Dependency Injection**: Explicit class constructor DI with `DIContainer` and `@injectable(deps=[...])`.
- **Pipeline Interceptors**: Build guards, middleware, interceptors, pipes, and exception filters for tool execution.
- **Asynchronous Background Tasks**: Spawn background workers automatically for long-running tools.
- **Built-in Authentication**: Modules for API Keys, JWT verification, and OAuth 2.1 (featuring Protected Resource Metadata discovery servers).
- **In-Process Testing Harness**: Run unit and integration tests against modules without managing subprocesses or real network transports.
- **CLI Tooling (`nitrostack-py`)**: Scaffold new apps, generate boilerplates, and run hot-reload development servers.

---

## Installation

```bash
pip install nitrostack
```

To install local developer or test dependencies:
```bash
pip install -e .
```

---

## Quick Start

### 1. Write your First Server

Create a file named `app.py`:

```python
import asyncio
from pydantic import BaseModel, Field
from nitrostack import (
    tool,
    resource,
    injectable,
    module,
    mcp_app,
    McpApplicationFactory,
    ServerConfig,
    ExecutionContext,
)

# 1. Input Validation Schema
class AddInput(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")

# 2. Injected Provider Service
@injectable(deps=[])
class CalculatorService:
    def add(self, a: float, b: float) -> float:
        return a + b

# 3. Controller
@injectable(deps=[CalculatorService])
class CalculatorController:
    def __init__(self, service: CalculatorService):
        self.service = service

    @tool(
        name="add",
        description="Add two numbers together",
        input_schema=AddInput
    )
    async def add(self, input: AddInput, context: ExecutionContext) -> float:
        context.logger.info(f"Adding {input.a} and {input.b}")
        return self.service.add(input.a, input.b)

    @resource(
        uri="calc://info",
        name="Calculator Info",
        description="Metadata about this calculator"
    )
    async def get_info(self, context: ExecutionContext) -> str:
        return "Simple Add Calculator v1.0.0"

# 4. Modules
@module(
    name="calculator",
    controllers=[CalculatorController],
    providers=[CalculatorService]
)
class CalculatorModule:
    pass

@module(
    name="app",
    imports=[CalculatorModule]
)
class AppModule:
    pass

# 5. Application Entrypoint
@mcp_app(
    module=AppModule,
    server=ServerConfig(name="math-server", version="1.0.0")
)
class App:
    pass

async def main():
    app = await McpApplicationFactory.create(App)
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Configure Environment Variables

The SDK reads standard settings from the environment or `.env` files:

| Environment Variable | Description |
|---|---|
| `PORT` / `MCP_SERVER_PORT` | The port to bind for HTTP/SSE transport (default: `8000`). |
| `MCP_TRANSPORT_TYPE` | Transport selection: `stdio`, `http`, or `dual` (combining stdio + HTTP/SSE). |
| `NODE_ENV` | If set to `production`, defaults to `dual` transport. Otherwise defaults to `stdio`. |
| `NITROSTACK_LOG_FILE` | Destination file for logs (default: `nitrostack.log`). |
| `NITROSTACK_LOG_LEVEL` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `NITROSTACK_LOG_TO_STDOUT` | Set to `true` to allow logging to stdout under stdio transport (Caution: may corrupt protocol stream). |

---

## Developing & Testing

### Running Tests
To run the automated test suite, execute:
```bash
python tests/test_basic.py
python tests/test_tasks.py
python tests/test_initial_tool.py
```

### Testing Harness
Write in-process unit tests using the harness:
```python
import asyncio
from nitrostack.testing import NitroTestingModule
from app import AppModule

async def test_add():
    harness = await NitroTestingModule.create(AppModule)
    result = await harness.call_tool("add", {"input": {"a": 5, "b": 10}})
    assert result == 15.0
    print("Test passed!")

if __name__ == "__main__":
    asyncio.run(test_add())
```
