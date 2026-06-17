# NitroStack Python SDK — Feature Specification

> Derived from `@nitrostack/core` TypeScript source.  
> This document defines what the Python SDK must implement, how each feature maps from TS, and what the Python-idiomatic API should look like.

---

## 1. MCP Primitives

### 1.1 Tools

**TS source:** `decorators.ts` → `@Tool()`, `tool.ts` → `Tool` class

Tools are the primary way an MCP server exposes functionality to AI clients.

**TS API:**
```typescript
@Tool({
  name: 'login',
  title: 'Login',
  description: 'Login with email and password',
  inputSchema: z.object({ email: z.string(), password: z.string() }),
  outputSchema: z.object({ token: z.string() }),
  annotations: { readOnlyHint: false, destructiveHint: false },
  taskSupport: 'optional',
})
async login(input: LoginInput, context: ExecutionContext) { ... }
```

**Python API:**
```python
@tool(
    name="login",
    title="Login",
    description="Login with email and password",
    input_schema=LoginInput,       # Pydantic model
    output_schema=LoginOutput,     # Pydantic model (optional)
    annotations=ToolAnnotations(read_only_hint=False),
    task_support="optional",
)
async def login(self, input: LoginInput, context: ExecutionContext): ...
```

**Fields to support:**

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Required |
| `title` | `str` | Optional, display name |
| `description` | `str` | Required |
| `input_schema` | Pydantic model or dict | Required. Call `.model_json_schema()` for wire format |
| `output_schema` | Pydantic model or dict | Optional |
| `annotations` | `ToolAnnotations` dataclass | Optional |
| `invocation` | `ToolInvocation` dataclass | Optional, for OpenAI Apps SDK UI messages |
| `task_support` | `"forbidden" \| "optional" \| "required"` | Default: `"forbidden"` |
| `visibility` | `"visible" \| "hidden"` | Default: `"visible"`, MCP Apps mode |
| `examples` | `ToolExamples` dataclass | Optional |
| `metadata` | dict | Optional, category/tags/rate_limit |

**`ToolAnnotations` fields (from `types.ts`):**

| Field | Default | Meaning |
|---|---|---|
| `destructive_hint` | `True` | Tool may make destructive changes |
| `idempotent_hint` | `False` | Repeated calls have no extra effect |
| `read_only_hint` | `False` | Tool does not modify environment |
| `open_world_hint` | `True` | Tool interacts with external entities |

**`@InitialTool()`** — marks a tool to be auto-called on client connection. Python equivalent: `@initial_tool` stacked with `@tool`.

---

### 1.2 Resources

**TS source:** `decorators.ts` → `@Resource()`

Resources expose readable data to AI clients (files, DB records, API data, etc.).

**TS API:**
```typescript
@Resource({
  uri: 'db://users/schema',
  name: 'User Schema',
  description: 'Database schema for users table',
  mimeType: 'application/json',
})
async getUserSchema(context: ExecutionContext) { ... }
```

**Python API:**
```python
@resource(
    uri="db://users/schema",
    name="User Schema",
    description="Database schema for users table",
    mime_type="application/json",
)
async def get_user_schema(self, context: ExecutionContext): ...
```

**Fields to support:**

| Field | Type | Notes |
|---|---|---|
| `uri` | `str` | Required. Static URI or template (e.g. `notes://note/{id}`) |
| `name` | `str` | Required |
| `title` | `str` | Optional |
| `description` | `str` | Required |
| `mime_type` | `str` | Optional, e.g. `"application/json"`, `"text/plain"` |
| `size` | `int` | Optional, bytes |
| `annotations` | `ResourceAnnotations` dataclass | Optional |
| `metadata.cacheable` | `bool` | Optional |
| `metadata.cache_max_age` | `int` | Optional, seconds |

**`ResourceAnnotations` fields:**

| Field | Type | Meaning |
|---|---|---|
| `audience` | `list["user" \| "assistant"]` | Intended consumer |
| `priority` | `float` | 0.0–1.0 importance |
| `last_modified` | `str` | ISO 8601 timestamp |

**Resource content return types** (discriminated union from `types.ts`):
```python
# Handler must return one of:
{"type": "text", "data": "..."}
{"type": "binary", "data": b"..."}
{"type": "json", "data": {...}}
```

---

### 1.3 Prompts

**TS source:** `decorators.ts` → `@Prompt()`

Prompt templates that AI clients can request to pre-fill conversation context.

**TS API:**
```typescript
@Prompt({
  name: 'auth-help',
  description: 'Help with authentication flows',
  arguments: [{ name: 'issue', description: 'The auth issue', required: true }],
})
async authHelp(args: PromptArgs, context: ExecutionContext) { ... }
```

**Python API:**
```python
@prompt(
    name="auth-help",
    description="Help with authentication flows",
    arguments=[PromptArgument(name="issue", description="The auth issue", required=True)],
)
async def auth_help(self, args: dict, context: ExecutionContext): ...
```

**`PromptMessage` return type** — handler must return a list of:
```python
PromptMessage(role="user" | "assistant" | "system", content="...")
```

---

## 2. Execution Pipeline

**TS source:** `tool.ts` → `Tool.execute()`

Every tool call runs through this chain in order. Any stage can abort execution.

```
ExceptionFilters (wrap everything)
  └── Guards          (can_activate → bool)
        └── Middleware  (use(ctx, next))
              └── Interceptors  (intercept(ctx, next))
                    └── Pipes         (transform(value, meta))
                          └── Handler (your function)
```

### 2.1 Guards

**TS source:** `guards/guard.interface.ts`

```python
# Protocol definition
class Guard(Protocol):
    async def can_activate(self, context: ExecutionContext) -> bool: ...

# Usage
@use_guards(ApiKeyGuard, MyCustomGuard)
@tool(...)
async def my_tool(self, input, context): ...
```

Return `False` → raises `"Access denied by guard"` error automatically.

**Built-in guards:**
- `ApiKeyGuard` — validates `x-api-key` from request metadata
- `JwtGuard` — validates Bearer JWT token, populates `context.auth`
- `OAuthGuard` — validates OAuth 2.1 access token with audience binding

---

### 2.2 Middleware

**TS source:** `middleware/middleware.interface.ts`

```python
class MyMiddleware:
    async def use(self, context: ExecutionContext, next: Callable) -> Any:
        # before
        result = await next()
        # after
        return result
```

---

### 2.3 Interceptors

**TS source:** `interceptors/interceptor.interface.ts`

```python
class MyInterceptor:
    async def intercept(self, context: ExecutionContext, next: Callable) -> Any:
        result = await next()
        # transform result
        return result
```

---

### 2.4 Pipes

**TS source:** `pipes/pipe.interface.ts`

```python
class MyPipe:
    async def transform(self, value: Any, metadata: PipeMetadata) -> Any:
        # validate or coerce
        return value
```

---

### 2.5 Exception Filters

**TS source:** `filters/exception-filter.interface.ts`

```python
class MyFilter:
    async def catch(self, error: Exception, context: ExecutionContext) -> Any:
        # handle and return fallback result
        return {"error": str(error)}
```

---

## 3. Module System

**TS source:** `module.ts`, `app-decorator.ts`

NestJS-style feature grouping. Each module declares its controllers and providers.

**TS API:**
```typescript
@Module({
  name: 'calculator',
  controllers: [CalculatorController],
  providers: [CalculatorService],
  imports: [ConfigModule],
  exports: [CalculatorService],
})
export class CalculatorModule {}
```

**Python API:**
```python
@module(
    name="calculator",
    controllers=[CalculatorController],
    providers=[CalculatorService],
    imports=[ConfigModule],
    exports=[CalculatorService],
)
class CalculatorModule: ...
```

---

## 4. App Entry Point

**TS source:** `app-decorator.ts` → `@McpApp`, `McpApplicationFactory`

**TS API:**
```typescript
@McpApp({ module: AppModule, server: { name: 'my-server', version: '1.0.0' } })
class App {}
const app = await McpApplicationFactory.create(App);
await app.start();
```

**Python API:**
```python
@mcp_app(module=AppModule, server=ServerConfig(name="my-server", version="1.0.0"))
class App: ...

async def main():
    app = await McpApplicationFactory.create(App)
    await app.start()

asyncio.run(main())
```

---

## 5. Dependency Injection

**TS source:** `di/container.ts`, `di/injectable.decorator.ts`

Global singleton `DIContainer`. All providers are singleton-scoped by default.

**TS API:**
```typescript
@Injectable()
export class CalculatorService {
  constructor(private config: ConfigService) {}
}
```

**Python API (explicit deps — always required, no auto-inference from type hints):**
```python
@injectable(deps=[ConfigService])
class CalculatorService:
    def __init__(self, config: ConfigService):
        self.config = config
```

**Container usage:**
```python
container = DIContainer.get_instance()
container.register(CalculatorService)
container.register_value("API_KEY", "my-key")
service = container.resolve(CalculatorService)
```

> **Note:** Python SDK always uses explicit `deps=[]`. Never attempt to auto-infer from type hints — this breaks under `from __future__ import annotations` (PEP 563).

---

## 6. Built-in Auth Modules

### 6.1 ApiKeyModule

**TS source:** `apikey-module.ts`

```python
ApiKeyModule.for_root(
    keys_env_prefix="API_KEY",   # reads API_KEY_1, API_KEY_2, etc.
    header_name="x-api-key",
    hashed=False,                # set True if storing SHA-256 hashes
)
```

Methods:
- `ApiKeyModule.get_keys()` → list of configured keys
- `ApiKeyModule.validate(key)` → `bool`
- `ApiKeyModule.hash_key(key)` → SHA-256 hex string
- `ApiKeyModule.generate_key(prefix="sk")` → `"sk_<random>"` secure key

---

### 6.2 JWTModule

**TS source:** `jwt-module.ts`

```python
JWTModule.for_root(
    secret_env_var="JWT_SECRET",
    expires_in="24h",
    audience="my-app",
    issuer="https://auth.example.com",
)
```

---

### 6.3 OAuthModule

**TS source:** `oauth-module.ts`

Full OAuth 2.1 compliance:
- RFC 9728 — Protected Resource Metadata (`/.well-known/oauth-protected-resource`)
- RFC 8414 — Authorization Server Metadata (`/.well-known/oauth-authorization-server`)
- RFC 8707 — Token audience binding
- RFC 7636 — PKCE
- RFC 7662 — Token introspection

```python
OAuthModule.for_root(
    resource_uri=os.environ["RESOURCE_URI"],
    authorization_servers=["https://auth.example.com"],
    scopes_supported=["mcp:read", "mcp:write", "tools:execute"],
    token_introspection_endpoint=os.environ.get("INTROSPECTION_ENDPOINT"),
    token_introspection_client_id=os.environ.get("INTROSPECTION_CLIENT_ID"),
    token_introspection_client_secret=os.environ.get("INTROSPECTION_CLIENT_SECRET"),
)
```

In stdio mode: starts a separate HTTP server on `OAUTH_DISCOVERY_PORT` (default 3005) to serve discovery endpoints, and notifies the client via stderr:
```
[NITROSTACK_OAUTH]{...}[/NITROSTACK_OAUTH]
```

---

### 6.4 ConfigModule

**TS source:** `config-module.ts`

```python
ConfigModule.for_root(
    env_file_path=".env",
    ignore_env_file=False,
    defaults={"LOG_LEVEL": "info"},
    validate=lambda cfg: "API_KEY" in cfg,
)

# Usage via injection:
@injectable(deps=[ConfigService])
class MyService:
    def __init__(self, config: ConfigService):
        self.api_key = config.get_or_throw("API_KEY")
```

> **Critical:** Parse `.env` manually — never use a library that writes to stdout. MCP stdio protocol uses stdout for JSON-RPC; any stray output breaks the connection.

---

## 7. Additional Decorators

**TS source:** `decorators/cache.decorator.ts`, `decorators/rate-limit.decorator.ts`, `decorators/health-check.decorator.ts`

### 7.1 Cache

```python
@cache(ttl=60)   # cache output for 60 seconds
@tool(...)
async def my_tool(self, input, context): ...
```

### 7.2 Rate Limit

```python
@rate_limit(max=10, window=60)   # 10 calls per 60 seconds per context
@tool(...)
async def my_tool(self, input, context): ...
```

### 7.3 Health Check

```python
@health_check("database")
def check_db(self) -> bool:
    return self.db.ping()
```

Health checks are exposed as a built-in MCP resource at `health://status`.

---

## 8. MCP Tasks (Async Long-Running Tools)

**TS source:** `task.ts`

For tools that take too long to complete synchronously. Server returns `taskId` immediately and runs the tool in the background.

**Task support levels:**
- `"forbidden"` (default) — tool cannot be invoked as a task
- `"optional"` — can be called normally or as a task
- `"required"` — must always be invoked as a task

**Progress reporting from inside the handler:**
```python
async def long_tool(self, input, context: ExecutionContext):
    if context.task:
        context.task.update_progress("Step 1 of 3...")
        context.task.throw_if_cancelled()
        # ... do work ...
        context.task.update_progress("Step 2 of 3...")
```

**MCP Task protocol methods exposed:**
- `tasks/get` — get task status
- `tasks/list` — list all tasks
- `tasks/cancel` — cancel a running task
- `tasks/result` — wait for and get task result

---

## 9. Events

**TS source:** `events/event-emitter.ts`, `events/event.decorator.ts`

Lightweight pub/sub event bus (singleton).

```python
@on_event("user.created")
async def handle_user_created(self, payload: dict): ...

# Emit from anywhere:
event_emitter = EventEmitter.get_instance()
await event_emitter.emit("user.created", {"id": 123})
```

---

## 10. Transports

**TS source:** `server.ts`, `transports/`

Auto-detected from environment variables. **Never write to stdout** — it carries the JSON-RPC wire protocol in stdio mode.

| Mode | When | How |
|---|---|---|
| `stdio` | `NODE_ENV` not set or `development` | Default, for Claude Desktop |
| `http` | `MCP_TRANSPORT_TYPE=http` | Streamable HTTP on `PORT` |
| `dual` | `NODE_ENV=production` | stdio + HTTP simultaneously |

**Env vars:**
- `PORT` / `MCP_SERVER_PORT` — HTTP server port
- `MCP_TRANSPORT_TYPE` — override transport
- `OAUTH_DISCOVERY_PORT` — OAuth discovery HTTP port (default 3005)

**HTTP endpoints:**
- `POST /mcp` — Streamable HTTP (primary)
- `GET /sse` + `POST /mcp/messages` — Legacy SSE (compatibility)

---

## 11. App Modes

**TS source:** `app-mode.ts`

Controlled by `NITROSTACK_APP_MODE` env var:

| Mode | Value | Use |
|---|---|---|
| Standard MCP | `mcp` (default) | Claude Desktop, standard clients |
| OpenAI Apps SDK | `openai` | OpenAI Assistants / ChatGPT plugins |
| MCP Apps Spec | `mcpapps` | MCP Apps spec compliance |

In `openai` mode, tool `_meta` uses `openai/*` keys. In `mcpapps` mode, uses `_meta.ui` format.

---

## 12. Execution Context

**TS source:** `types.ts` → `ExecutionContext`

Passed to every handler, guard, middleware, interceptor, pipe, and filter.

```python
@dataclass
class ExecutionContext:
    request_id: str           # unique request ID for tracing
    tool_name: str | None     # name of tool being executed
    logger: Logger            # structured logger (file only, never stdout)
    metadata: dict            # raw request metadata
    auth: AuthContext | None  # populated if authenticated
    task: TaskContext | None  # populated for async task execution
```

**`AuthContext` fields:**
```python
@dataclass
class AuthContext:
    subject: str | None       # user/client identifier
    scopes: list[str]         # granted permissions
    client_id: str | None     # machine-to-machine
    exp: int | None           # expiration timestamp
    iat: int | None           # issued-at timestamp
    iss: str | None           # issuer URL
    claims: dict              # custom claims
    token_payload: Any        # full decoded token
```

---

## 13. Logger

**TS source:** `logger.ts`

Structured logger — **stdout disabled**, writes to file only.

```python
class Logger(Protocol):
    def debug(self, message: str, meta: dict | None = None) -> None: ...
    def info(self, message: str, meta: dict | None = None) -> None: ...
    def warn(self, message: str, meta: dict | None = None) -> None: ...
    def error(self, message: str, meta: dict | None = None) -> None: ...
```

Recommended implementation: `loguru` or `structlog` with file-only sink.

---

## 14. Error Types

**TS source:** `errors.ts`

```python
class ToolExecutionError(Exception): ...
class ValidationError(Exception): ...
class ResourceNotFoundError(Exception): ...
class PromptNotFoundError(Exception): ...
```

Errors in tool execution are returned as `isError: True` MCP responses, not protocol-level errors.

---

## 15. Testing Module

**TS source:** `testing/index.ts`

In-process test harness — no real transport, no subprocess.

```python
async def test_add_tool():
    module = await NitroTestingModule.create(AppModule)
    result = await module.call_tool("add", {"a": 2, "b": 3})
    assert result == 5

    resource = await module.read_resource("notes://all")
    assert resource is not None

    prompt = await module.get_prompt("summarise", {"text": "hello"})
    assert len(prompt.messages) > 0
```

---

## 16. CLI (`nitrostack-py`)

Equivalent of `@nitrostack/cli` for Python projects.

| Command | What it does |
|---|---|
| `nitrostack-py init my-server` | Scaffold new Python MCP server |
| `nitrostack-py dev` | Hot-reload dev server (uses `watchfiles`) |
| `nitrostack-py start` | Run the server |
| `nitrostack-py generate tool <name>` | Generate tool boilerplate |
| `nitrostack-py generate module <name>` | Generate module boilerplate |

**Starter template structure:**
```
my-server/
├── main.py
├── app.module.py
├── modules/
│   └── calculator/
│       ├── calculator.module.py
│       ├── calculator.tools.py
│       └── calculator.service.py
├── .env
└── requirements.txt
```

---

## 17. Python Stack Decisions

| TypeScript | Python equivalent | Reason |
|---|---|---|
| Zod | Pydantic v2 | Direct equivalent, built-in JSON Schema |
| `reflect-metadata` | Attributes on functions/classes | No runtime metadata system in Python |
| `emitDecoratorMetadata` | Explicit `deps=[]` always | PEP 563 makes type hint inference unreliable |
| Parameter decorators `@Inject()` | `deps=[]` in `@injectable` | Python has no parameter decorators |
| TypeScript interfaces | `typing.Protocol` | Structural subtyping |
| `winston` logger | `loguru` or `structlog` | File-only sink, no stdout |
| `@modelcontextprotocol/sdk` | `mcp` (official Python SDK) | Build on top, don't reimplement transport |
| Next.js widgets | Skip in v1 | Deeply Node.js-specific, not relevant to Python backend |

---

## 18. What Python SDK Does NOT Port (v1 scope)

| Feature | Reason |
|---|---|
| `@Widget()` and React component serving | Requires Next.js build pipeline — Node.js only |
| `@modelcontextprotocol/sdk` transport internals | The official `mcp` Python package handles this |
| `emitDecoratorMetadata` auto-DI | No Python equivalent; use explicit `deps=[]` |
| Parameter decorators (`@Inject()`) | Python language limitation |
| PostHog analytics in CLI | Nice-to-have, v2 |

---

## 19. Deployment (No Managed Cloud)

NitroStack has no proprietary hosting. The Python SDK follows the same model — bring your own infrastructure.

**What the SDK provides for deployment:**
- Environment-based transport switching (`MCP_TRANSPORT_TYPE`)
- OAuth 2.1 for remote authenticated deployments
- Port config via env vars (`PORT`, `MCP_SERVER_PORT`, `OAUTH_DISCOVERY_PORT`)
- Health check endpoints for load balancers
- Structured file logging (no stdout pollution)

**Tested deployment targets:** Railway, Fly.io, Render, any Docker/container host.
