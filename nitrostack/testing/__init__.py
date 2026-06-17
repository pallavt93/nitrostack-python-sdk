from typing import Type, Any
from nitrostack.core.app import mcp_app, McpApplicationFactory, ServerConfig, McpApplication

class NitroTestingModule:
    """
    In-process test harness for testing NitroStack applications
    without spinning up real transports or subprocesses (Section 15).
    """
    @classmethod
    async def create(cls, app_module: Type) -> "NitroTestingModule":
        # Construct a dummy App class decorated with @mcp_app
        @mcp_app(module=app_module, server=ServerConfig(name="test-server"))
        class TestApp:
            pass

        app = await McpApplicationFactory.create(TestApp)
        return cls(app)

    def __init__(self, app: McpApplication):
        self.app = app

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Calls a tool by name in the test harness, returning the raw or deserialized result."""
        if not self.app.mcp_server:
            raise RuntimeError("Application has not been bootstrapped.")
        res = await self.app.mcp_server.call_tool(name, arguments)
        
        # FastMCP returns a list of ContentBlocks. Let's unpack the first TextContent.
        if isinstance(res, list) and len(res) > 0:
            block = res[0]
            if hasattr(block, "text"):
                text_val = block.text
                import json
                try:
                    return json.loads(text_val)
                except Exception:
                    return text_val
        return res

    async def read_resource(self, uri: str) -> Any:
        """Reads a resource by URI in the test harness, returning raw text or deserialized JSON."""
        if not self.app.mcp_server:
            raise RuntimeError("Application has not been bootstrapped.")
        res = await self.app.mcp_server.read_resource(uri)
        
        # FastMCP returns a list of ReadResourceContents or a result object
        content_list = []
        if isinstance(res, list):
            content_list = res
        elif hasattr(res, "contents"):
            content_list = res.contents

        if content_list and len(content_list) > 0:
            content_block = content_list[0]
            text_val = None
            if hasattr(content_block, "content"):
                text_val = content_block.content
            elif hasattr(content_block, "text"):
                text_val = content_block.text
                
            if text_val is not None:
                import json
                try:
                    return json.loads(text_val)
                except Exception:
                    return text_val
        return res

    async def get_prompt(self, name: str, arguments: dict) -> Any:
        """Retrieves a prompt by name in the test harness, returning prompt messages."""
        if not self.app.mcp_server:
            raise RuntimeError("Application has not been bootstrapped.")
        res = await self.app.mcp_server.get_prompt(name, arguments)
        # FastMCP get_prompt returns a GetPromptResult which has messages list
        if hasattr(res, "messages"):
            return res.messages
        return res
