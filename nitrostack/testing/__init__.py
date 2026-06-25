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
        
        # FastMCP returns a list of ContentBlocks, or a tuple of (list[ContentBlock], meta)
        content_list = res
        if isinstance(res, tuple) and len(res) > 0:
            content_list = res[0]

        if isinstance(content_list, list) and len(content_list) > 0:
            block = content_list[0]
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
        res_obj = res[0] if isinstance(res, tuple) and len(res) > 0 else res
        
        if isinstance(res_obj, list):
            content_list = res_obj
        elif hasattr(res_obj, "contents"):
            content_list = res_obj.contents

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
        
        res_obj = res[0] if isinstance(res, tuple) and len(res) > 0 else res
        
        # FastMCP get_prompt returns a GetPromptResult which has messages list
        if hasattr(res_obj, "messages"):
            return res_obj.messages
        return res
