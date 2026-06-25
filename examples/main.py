import asyncio
from pydantic import BaseModel, Field
from nitrostack import tool, injectable, module, mcp_app, McpApplicationFactory, ServerConfig, ExecutionContext

# 1. Define the input schema
class GreetInput(BaseModel):
    name: str = Field(description="Name of the person to greet")

# 2. Build the greeting controller
@injectable()
class GreetController:
    @tool(
        name="greet",
        description="Generates a greeting message",
        input_schema=GreetInput
    )
    async def greet(self, input: GreetInput, context: ExecutionContext) -> str:
        context.logger.info(f"Greeting: {input.name}")
        return f"Welcome to the Model Context Protocol, {input.name}!"

# 3. Register under the AppModule
@module(name="app", controllers=[GreetController])
class AppModule:
    pass

# 4. Define Server config and bootstrap
@mcp_app(module=AppModule, server=ServerConfig(name="greeting-server", version="1.0.0"))
class App:
    pass

async def main():
    app = await McpApplicationFactory.create(App)
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())