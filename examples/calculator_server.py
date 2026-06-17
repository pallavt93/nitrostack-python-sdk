import asyncio
import os
import sys
from typing import Literal, Dict, Any, List
from pydantic import BaseModel, Field

# Ensure parent directory is in sys.path so nitrostack can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nitrostack import (
    tool,
    resource,
    prompt,
    injectable,
    module,
    mcp_app,
    McpApplicationFactory,
    ServerConfig,
    ExecutionContext,
    PromptArgument,
    PromptMessage,
    ConfigModule,
    ConfigService,
    health_check,
)

# 1. Input Schemas using Pydantic (Section 17)
class CalculateInput(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")
    operation: Literal["add", "subtract", "multiply", "divide"] = Field(
        description="The arithmetic operation to perform"
    )

class ConvertTempInput(BaseModel):
    value: float = Field(description="Temperature value to convert")
    from_unit: Literal["celsius", "fahrenheit", "kelvin"] = Field(description="Source temperature unit")
    to_unit: Literal["celsius", "fahrenheit", "kelvin"] = Field(description="Target temperature unit")


# 2. Injected Services (Section 5)
@injectable(deps=[ConfigService])
class CalculatorService:
    def __init__(self, config: ConfigService):
        self.config = config
        # Read a dummy precision config from env or defaults
        self.precision = int(self.config.get("CALC_PRECISION", 4))

    def calculate(self, a: float, b: float, op: str) -> float:
        if op == "add":
            res = a + b
        elif op == "subtract":
            res = a - b
        elif op == "multiply":
            res = a * b
        elif op == "divide":
            if b == 0:
                raise ValueError("Division by zero")
            res = a / b
        else:
            raise ValueError(f"Unknown operation {op}")
        return round(res, self.precision)

    def convert_temp(self, value: float, from_u: str, to_u: str) -> float:
        # Convert to Celsius first
        if from_u == "celsius":
            c = value
        elif from_u == "fahrenheit":
            c = (value - 32) * 5 / 9
        else:  # kelvin
            c = value - 273.15

        # Convert from Celsius to target
        if to_u == "celsius":
            res = c
        elif to_u == "fahrenheit":
            res = c * 9 / 5 + 32
        else:  # kelvin
            res = c + 273.15
            
        return round(res, self.precision)


# 3. Controllers exposing MCP endpoints (Section 3)
@injectable(deps=[CalculatorService])
class CalculatorController:
    def __init__(self, calc_service: CalculatorService):
        self.calc_service = calc_service

    # MCP Tool: calculate (Section 1.1)
    @tool(
        name="calculate",
        title="Calculate",
        description="Perform basic arithmetic calculations (add, subtract, multiply, divide)",
        input_schema=CalculateInput
    )
    async def calculate(self, input: CalculateInput, context: ExecutionContext) -> Dict[str, Any]:
        context.logger.info(f"Executing calculation: {input.a} {input.operation} {input.b}")
        try:
            result = self.calc_service.calculate(input.a, input.b, input.operation)
            return {"result": result, "status": "success"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}

    # MCP Tool: convert_temperature
    @tool(
        name="convert_temperature",
        title="Convert Temperature",
        description="Convert temperature units (celsius, fahrenheit, kelvin)",
        input_schema=ConvertTempInput
    )
    async def convert_temperature(self, input: ConvertTempInput, context: ExecutionContext) -> Dict[str, Any]:
        context.logger.info(f"Converting temperature: {input.value} from {input.from_unit} to {input.to_unit}")
        result = self.calc_service.convert_temp(input.value, input.from_unit, input.to_unit)
        return {"result": result, "unit": input.to_unit}

    # MCP Resource: operations (Section 1.2)
    @resource(
        uri="calculator://operations",
        name="Calculator Operations",
        description="List of supported arithmetic operations",
        mime_type="application/json"
    )
    async def get_operations(self, context: ExecutionContext) -> Dict[str, Any]:
        return {
            "supported_operations": ["add", "subtract", "multiply", "divide"],
            "parameters": ["a", "b"]
        }

    # MCP Resource: results template
    @resource(
        uri="calculator://results/{result_id}",
        name="Calculator Result",
        description="Detailed breakdown of a specific calculation result",
        mime_type="text/plain"
    )
    async def get_result_detail(self, result_id: str, context: ExecutionContext) -> str:
        # Mock calculation details for ID
        return f"Breakdown for calculation {result_id}:\nOperation: add\nResult: 42.0\nStatus: completed"

    # MCP Resource: widget examples
    @resource(
        uri="widget://examples",
        name="Widget Examples",
        description="UI widget schema examples for rendering calculator widgets",
        mime_type="application/json"
    )
    async def get_widget_examples(self, context: ExecutionContext) -> Dict[str, Any]:
        return {
            "widget": "CalculatorWidget",
            "theme": "dark",
            "layouts": ["grid", "scientific"]
        }

    # MCP Prompt: calculator_help (Section 1.3)
    @prompt(
        name="calculator_help",
        description="Get help with calculator operations",
        arguments=[PromptArgument(name="operation", description="The operation to get help on", required=True)]
    )
    async def get_calculator_help(self, args: dict, context: ExecutionContext) -> List[PromptMessage]:
        op = args.get("operation", "add")
        help_texts = {
            "add": "The 'add' tool sums parameter 'a' and 'b'. Example: a=10, b=5 yields 15.",
            "subtract": "The 'subtract' tool calculates 'a' minus 'b'. Example: a=10, b=5 yields 5.",
            "multiply": "The 'multiply' tool multiplies 'a' and 'b'. Example: a=10, b=5 yields 50.",
            "divide": "The 'divide' tool divides 'a' by 'b'. Note: 'b' must not be zero."
        }
        text = help_texts.get(op, f"No specific help found for '{op}'. Supported: add, subtract, multiply, divide.")
        return [
            PromptMessage(role="user", content="You are a helpful mathematical assistant."),
            PromptMessage(role="user", content=text)
        ]

    # Health Check (Section 7.3)
    @health_check("calculator_engine")
    def check_engine(self) -> bool:
        # Simple status check verification
        return self.calc_service.precision >= 0


# 4. Modules grouping controllers and services (Section 3)
@module(
    name="calculator",
    controllers=[CalculatorController],
    providers=[CalculatorService],
    exports=[CalculatorService]
)
class CalculatorModule:
    pass


# 5. Root AppModule (Section 3)
@module(
    name="app",
    imports=[
        CalculatorModule,
        ConfigModule.for_root(
            env_file_path=".env",
            defaults={"CALC_PRECISION": "4", "PORT": "8080"}
        )
    ]
)
class AppModule:
    pass


# 6. Main App Class Entrypoint (Section 4)
@mcp_app(
    module=AppModule,
    server=ServerConfig(name="my-server", version="1.0.0")
)
class App:
    pass


async def main():
    import sys
    sys.stderr.write("Initializing NitroStack Python Server...\n")
    sys.stderr.flush()
    app = await McpApplicationFactory.create(App)
    sys.stderr.write("Starting server over stdio...\n")
    sys.stderr.flush()
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())
