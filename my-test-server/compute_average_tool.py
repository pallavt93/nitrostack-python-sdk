from nitrostack import tool, ExecutionContext
from pydantic import BaseModel

class ComputeAverageInput(BaseModel):
    # Add input parameters here
    pass

@tool(
    name="compute_average",
    description="Implement your tool description here",
    input_schema=ComputeAverageInput
)
async def compute_average_handler(input: ComputeAverageInput, context: ExecutionContext):
    context.logger.info("Executing tool compute_average")
    return {"status": "success"}
