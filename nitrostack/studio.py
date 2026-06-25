import asyncio
import os
import sys
import json
import webbrowser
from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.staticfiles import StaticFiles
from starlette.responses import JSONResponse, HTMLResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.exceptions import HTTPException

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ReadResourceResult, GetPromptResult

# Global State
class StudioState:
    session: Optional[ClientSession] = None
    exit_stack: Optional[AsyncExitStack] = None
    client_task: Optional[asyncio.Task] = None
    connected: bool = False
    log_queue: asyncio.Queue = asyncio.Queue()
    active_websockets: List[WebSocket] = []
    target_command: str = "python"
    target_script: str = "examples/calculator_server.py"
    connection_error: Optional[str] = None

state = StudioState()

# Log wrapping stream decorators
class LoggingReceiveStream:
    def __init__(self, stream, log_callback):
        self._stream = stream
        self._log = log_callback
        
    async def receive(self):
        item = await self._stream.receive()
        try:
            if hasattr(item, "model_dump_json"):
                self._log(f"<-- recv:\n{item.model_dump_json(indent=2)}")
            else:
                self._log(f"<-- recv: {str(item)}")
        except Exception as e:
            self._log(f"SYSTEM: Error logging received item: {e}")
        return item
        
    async def aclose(self):
        await self._stream.aclose()

    async def __aenter__(self):
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self._stream, "__aexit__"):
            await self._stream.__aexit__(exc_type, exc_val, exc_tb)

    def __aiter__(self):
        return self

    async def __anext__(self):
        import anyio
        try:
            return await self.receive()
        except anyio.EndOfStream:
            raise StopAsyncIteration
        except Exception as e:
            if "EndOfStream" in type(e).__name__:
                raise StopAsyncIteration
            raise e

class LoggingSendStream:
    def __init__(self, stream, log_callback):
        self._stream = stream
        self._log = log_callback
        
    async def send(self, item):
        try:
            if hasattr(item, "model_dump_json"):
                self._log(f"--> send:\n{item.model_dump_json(indent=2)}")
            else:
                self._log(f"--> send: {str(item)}")
        except Exception as e:
            self._log(f"SYSTEM: Error logging sent item: {e}")
        await self._stream.send(item)
        
    async def aclose(self):
        await self._stream.aclose()

    async def __aenter__(self):
        if hasattr(self._stream, "__aenter__"):
            await self._stream.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self._stream, "__aexit__"):
            await self._stream.__aexit__(exc_type, exc_val, exc_tb)


def push_log(msg: str):
    print(msg, file=sys.stderr)
    asyncio.create_task(state.log_queue.put(msg))


async def broadcast_logs():
    """Background task to broadcast logs from queue to all WebSockets."""
    while True:
        msg = await state.log_queue.get()
        disconnected = []
        for ws in state.active_websockets:
            try:
                await ws.send_text(msg)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in state.active_websockets:
                state.active_websockets.remove(ws)
        state.log_queue.task_done()


async def run_client_loop(command: str, script_path: str):
    state.exit_stack = AsyncExitStack()
    state.connection_error = None
    push_log(f"SYSTEM: Spawning subprocess '{command} {script_path}'...")
    try:
        server_params = StdioServerParameters(
            command=command,
            args=[script_path],
            env={
                "PYTHONPATH": os.path.abspath("."),
                "NODE_ENV": "development"
            }
        )
        read, write = await state.exit_stack.enter_async_context(stdio_client(server_params))
        
        logged_read = LoggingReceiveStream(read, push_log)
        logged_write = LoggingSendStream(write, push_log)
        
        push_log("SYSTEM: Initializing ClientSession...")
        state.session = await state.exit_stack.enter_async_context(
            ClientSession(logged_read, logged_write)
        )
        await state.session.initialize()
        state.connected = True
        push_log("SYSTEM: Connected to MCP server over STDIO successfully!")
        
        while state.connected:
            await asyncio.sleep(0.5)
            
    except Exception as e:
        state.connection_error = str(e)
        push_log(f"SYSTEM_ERROR: Connection failed: {e}")
        state.connected = False
        state.session = None
    finally:
        push_log("SYSTEM: Closing session and subprocess streams...")
        await state.exit_stack.aclose()
        state.connected = False
        state.session = None
        push_log("SYSTEM: Disconnected.")


# Starlette REST Endpoints
async def connect(request):
    if state.connected:
        return JSONResponse({"status": "already_connected"})
        
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    command = body.get("command", "python")
    script_path = body.get("script_path", "examples/calculator_server.py")
    
    # Resolve 'python' / 'python3' to sys.executable to ensure we use the same environment
    # and avoid Windows App Store path alias hangs.
    resolved_command = command
    if command in ("python", "python3"):
        resolved_command = sys.executable
        
    state.target_command = command
    state.target_script = script_path
    
    # If the script path is a directory, resolve to its main.py, app_module.py, or any nitro file
    resolved_script = script_path
    if os.path.isdir(script_path):
        if os.path.exists(os.path.join(script_path, "main.py")):
            resolved_script = os.path.join(script_path, "main.py")
        elif os.path.exists(os.path.join(script_path, "app_module.py")):
            resolved_script = os.path.join(script_path, "app_module.py")
        else:
            try:
                for item in os.listdir(script_path):
                    if item.endswith(".py"):
                        file_path = os.path.join(script_path, item)
                        if os.path.isfile(file_path) and is_nitro_file(file_path):
                            resolved_script = file_path
                            break
            except Exception:
                pass
                
    state.client_task = asyncio.create_task(
        run_client_loop(resolved_command, resolved_script)
    )
    
    # Wait up to 5 seconds for connection
    for _ in range(10):
        if state.connected:
            return JSONResponse({"status": "connected"})
        if state.client_task.done():
            break
        await asyncio.sleep(0.5)
        
    if state.connected:
        return JSONResponse({"status": "connected"})
    
    error_detail = state.connection_error or "Unknown error spawning or initializing MCP server subprocess."
    return JSONResponse({
        "status": "failed",
        "detail": f"Failed to connect to MCP server: {error_detail}"
    }, status_code=500)


async def disconnect(request):
    if not state.connected:
        return JSONResponse({"status": "already_disconnected"})
    state.connected = False
    if state.client_task:
        state.client_task.cancel()
    return JSONResponse({"status": "disconnected"})


async def get_status(request):
    return JSONResponse({
        "connected": state.connected,
        "command": state.target_command,
        "script_path": state.target_script
    })


async def get_tools(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    try:
        tools_res = await state.session.list_tools()
        return JSONResponse({"tools": [t.model_dump(mode="json") for t in tools_res.tools]})
    except Exception as e:
        return JSONResponse({"status": "failed", "error": f"Error listing tools: {e}"}, status_code=500)


async def get_resources(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    try:
        resources_res = await state.session.list_resources()
        templates_res = await state.session.list_resource_templates()
        return JSONResponse({
            "resources": [r.model_dump(mode="json") for r in resources_res.resources],
            "templates": [t.model_dump(mode="json") for t in templates_res.resourceTemplates]
        })
    except Exception as e:
        return JSONResponse({"status": "failed", "error": f"Error listing resources: {e}"}, status_code=500)


async def get_prompts(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    try:
        prompts_res = await state.session.list_prompts()
        return JSONResponse({"prompts": [p.model_dump(mode="json") for p in prompts_res.prompts]})
    except Exception as e:
        return JSONResponse({"status": "failed", "error": f"Error listing prompts: {e}"}, status_code=500)


async def call_tool(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    try:
        body = await request.json()
        name = body.get("name")
        arguments = body.get("arguments", {})
        res = await state.session.call_tool(name, arguments)
        return JSONResponse(res.model_dump(mode="json"))
    except Exception as e:
        return JSONResponse({"status": "failed", "error": f"Error calling tool: {e}"}, status_code=500)


async def read_resource(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    try:
        body = await request.json()
        uri = body.get("uri")
        res = await state.session.read_resource(uri)
        return JSONResponse(res.model_dump(mode="json"))
    except Exception as e:
        return JSONResponse({"status": "failed", "error": f"Error reading resource: {e}"}, status_code=500)


async def get_prompt(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    try:
        body = await request.json()
        name = body.get("name")
        arguments = body.get("arguments", {})
        res = await state.session.get_prompt(name, arguments)
        return JSONResponse(res.model_dump(mode="json"))
    except Exception as e:
        return JSONResponse({"status": "failed", "error": f"Error getting prompt: {e}"}, status_code=500)


async def chat(request):
    if not state.connected or not state.session:
        raise HTTPException(status_code=400, detail="Server is not connected")
    
    try:
        body = await request.json()
        msg_raw = body.get("message", "")
    except Exception:
        msg_raw = ""
        
    msg_stripped = msg_raw.strip()
    if not msg_stripped:
        return JSONResponse({"response": "Please enter a message.", "tool_called": None})

    api_key = os.environ.get("OPENAI_API_KEY")
    
    # LLM-driven path if API key is present
    if api_key:
        import httpx
        try:
            push_log("CHAT_AGENT: Querying MCP tools list...")
            tools_res = await state.session.list_tools()
            
            openai_tools = []
            for t in tools_res.tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema
                    }
                })
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant with access to tools via Model Context Protocol. Help the user by calling appropriate tools if needed. Always respond in natural language. If you call a tool, keep your explanation concise."
                    },
                    {"role": "user", "content": msg_stripped}
                ]
            }
            if openai_tools:
                payload["tools"] = openai_tools
                payload["tool_choice"] = "auto"
                
            push_log(f"CHAT_AGENT: Sending request to OpenAI API with {len(openai_tools)} tools...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"OpenAI API returned status {response.status_code}: {response.text}")
                    
                res_data = response.json()
                message = res_data["choices"][0]["message"]
                
                # Check if LLM decided to invoke a tool
                if message.get("tool_calls"):
                    tool_call = message["tool_calls"][0]
                    tool_name = tool_call["function"]["name"]
                    tool_args_str = tool_call["function"]["arguments"]
                    
                    try:
                        tool_args = json.loads(tool_args_str)
                    except Exception:
                        tool_args = {}
                        
                    push_log(f"CHAT_AGENT: LLM decided to invoke tool '{tool_name}' with args: {tool_args_str}")
                    
                    # Execute the tool call on the connected MCP server
                    tool_res = await state.session.call_tool(tool_name, tool_args)
                    content_text = ""
                    if tool_res.content and len(tool_res.content) > 0:
                        content_text = tool_res.content[0].text
                        
                    push_log(f"CHAT_AGENT: Tool output returned: {content_text}. Requesting LLM summary...")
                    
                    # Send tool output back to LLM to get a natural language summary
                    follow_up_payload = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system", 
                                "content": "You are a helpful assistant with access to tools via Model Context Protocol. Summarize the tool result nicely for the user."
                            },
                            {"role": "user", "content": msg_stripped},
                            message,
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": content_text
                            }
                        ]
                    }
                    
                    follow_up_res = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=follow_up_payload,
                        timeout=30.0
                    )
                    
                    if follow_up_res.status_code != 200:
                        raise Exception(f"OpenAI follow-up API returned status {follow_up_res.status_code}")
                        
                    final_res_data = follow_up_res.json()
                    final_response = final_res_data["choices"][0]["message"]["content"]
                    
                    return JSONResponse({
                        "response": final_response,
                        "tool_called": tool_name,
                        "arguments": tool_args,
                        "output": content_text
                    })
                else:
                    # No tool call made, return direct text response
                    final_response = message["content"]
                    return JSONResponse({
                        "response": final_response,
                        "tool_called": None
                    })
        except Exception as e:
            push_log(f"CHAT_AGENT_ERROR: OpenAI tool calling failed: {e}. Falling back to offline matcher...")
            # Fall through to offline regex path on failure

    # Offline path (retained for fallback/testing without key)
    msg = msg_stripped.lower()
    
    import re
    add_match = re.search(r"(\d+(\.\d+)?)\s*(?:add|plus|\+)\s*(\d+(\.\d+)?)", msg)
    sub_match = re.search(r"(\d+(\.\d+)?)\s*(?:subtract|minus|\-)\s*(\d+(\.\d+)?)", msg)
    mul_match = re.search(r"(\d+(\.\d+)?)\s*(?:multiply|times|\*)\s*(\d+(\.\d+)?)", msg)
    div_match = re.search(r"(\d+(\.\d+)?)\s*(?:divide|by|/)\s*(\d+(\.\d+)?)", msg)
    temp_match = re.search(r"convert\s*(\d+(\.\d+)?)\s*(celsius|fahrenheit|kelvin)\s*(?:to)\s*(celsius|fahrenheit|kelvin)", msg)
    
    tool_triggered = None
    arguments = {}
    
    if add_match:
        a = float(add_match.group(1))
        b = float(add_match.group(3))
        tool_triggered = "calculate"
        arguments = {"input": {"a": a, "b": b, "operation": "add"}}
    elif sub_match:
        a = float(sub_match.group(1))
        b = float(sub_match.group(3))
        tool_triggered = "calculate"
        arguments = {"input": {"a": a, "b": b, "operation": "subtract"}}
    elif mul_match:
        a = float(mul_match.group(1))
        b = float(mul_match.group(3))
        tool_triggered = "calculate"
        arguments = {"input": {"a": a, "b": b, "operation": "multiply"}}
    elif div_match:
        a = float(div_match.group(1))
        b = float(div_match.group(3))
        tool_triggered = "calculate"
        arguments = {"input": {"a": a, "b": b, "operation": "divide"}}
    elif temp_match:
        val = float(temp_match.group(1))
        from_u = temp_match.group(3)
        to_u = temp_match.group(4)
        tool_triggered = "convert_temperature"
        arguments = {"input": {"value": val, "from_unit": from_u, "to_unit": to_u}}

    if tool_triggered:
        push_log(f"CHAT_AGENT: User request matched offline rule for tool '{tool_triggered}'. Invoking...")
        try:
            res = await state.session.call_tool(tool_triggered, arguments)
            content_text = ""
            if res.content and len(res.content) > 0:
                content_text = res.content[0].text
                
            try:
                parsed_res = json.loads(content_text)
                if "result" in parsed_res:
                    answer = f"I invoked the tool `{tool_triggered}` with parameters `{json.dumps(arguments['input'])}`.\nThe computed result is **{parsed_res['result']}**."
                else:
                    answer = f"I called `{tool_triggered}`. Output: {content_text}"
            except Exception:
                answer = f"Called `{tool_triggered}` successfully. Output: {content_text}"
                
            return JSONResponse({
                "response": answer,
                "tool_called": tool_triggered,
                "arguments": arguments,
                "output": content_text
            })
        except Exception as e:
            return JSONResponse({
                "response": f"I attempted to call `{tool_triggered}` but failed: {e}",
                "tool_called": tool_triggered,
                "arguments": arguments,
                "error": str(e)
            })
            
    return JSONResponse({
        "response": "Hello! I am the NitroStack Agent. Ask me to perform a calculation (e.g. 'add 10 and 20') or convert temperature (e.g. 'convert 100 celsius to fahrenheit'). To enable generic LLM-driven tool calling with any server, please set the OPENAI_API_KEY environment variable.",
        "tool_called": None
    })


# WebSockets Log stream
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    state.active_websockets.append(websocket)
    push_log(f"SYSTEM: Client UI connected to RPC Logs WebSocket stream.")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in state.active_websockets:
            state.active_websockets.remove(websocket)
        push_log("SYSTEM: Client UI disconnected from RPC Logs WebSocket stream.")


def is_nitro_dir(dir_path: str) -> bool:
    try:
        if not os.path.isdir(dir_path):
            return False
        if os.path.exists(os.path.join(dir_path, "app_module.py")) or os.path.exists(os.path.join(dir_path, "main.py")):
            return True
        for item in os.listdir(dir_path):
            if item.endswith(".py"):
                file_path = os.path.join(dir_path, item)
                if os.path.isfile(file_path):
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(1024)
                        if "import nitrostack" in content or "from nitrostack" in content:
                            return True
    except Exception:
        pass
    return False

def is_nitro_file(file_path: str) -> bool:
    if not os.path.isfile(file_path) or not file_path.endswith(".py"):
        return False
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(1024)
            return "import nitrostack" in content or "from nitrostack" in content or "@mcp_app" in content or "@module" in content
    except Exception:
        return False

async def fs_list(request):
    try:
        path = request.query_params.get("path")
        if not path:
            path = os.path.expanduser("~")
        path = os.path.abspath(path)
        if not os.path.exists(path) or not os.path.isdir(path):
            return JSONResponse({"error": f"Path {path} does not exist or is not a directory"}, status_code=400)
            
        items = []
        try:
            for name in os.listdir(path):
                if name.startswith(".") and name not in (".env"):
                    continue
                full_path = os.path.join(path, name)
                is_dir = os.path.isdir(full_path)
                is_nitro = False
                if is_dir:
                    is_nitro = is_nitro_dir(full_path)
                else:
                    is_nitro = is_nitro_file(full_path)
                items.append({
                    "name": name,
                    "path": full_path.replace(os.sep, "/"),
                    "is_dir": is_dir,
                    "is_nitro": is_nitro
                })
        except PermissionError:
            return JSONResponse({"error": f"Permission denied accessing path {path}"}, status_code=403)
            
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        favorites = {
            "Home": os.path.expanduser("~").replace(os.sep, "/"),
            "Desktop": os.path.join(os.path.expanduser("~"), "Desktop").replace(os.sep, "/"),
            "Documents": os.path.join(os.path.expanduser("~"), "Documents").replace(os.sep, "/"),
        }
        favorites = {k: v for k, v in favorites.items() if os.path.exists(v)}
        
        return JSONResponse({
            "current_path": path.replace(os.sep, "/"),
            "items": items,
            "favorites": favorites
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def fs_create(request):
    try:
        body = await request.json()
        parent_path = body.get("parent_path")
        name = body.get("name")
        if not parent_path or not name:
            return JSONResponse({"error": "parent_path and name are required"}, status_code=400)
        target_path = os.path.join(parent_path, name)
        if os.path.exists(target_path):
            return JSONResponse({"error": f"Directory {target_path} already exists"}, status_code=400)
        old_cwd = os.getcwd()
        try:
            os.chdir(parent_path)
            from nitrostack.cli.main import init_project
            init_project(name)
        finally:
            os.chdir(old_cwd)
        return JSONResponse({"status": "success", "project_path": target_path.replace(os.sep, "/")})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def detect_projects(request):
    detected = []
    try:
        for root, dirs, files in os.walk("."):
            # Skip hidden folders, venv, env, static, cache, etc.
            if any(part.startswith(".") or part in ("venv", "env", "__pycache__", "static", "nitrostack", "tests") for part in root.split(os.sep)):
                continue
            for file in files:
                if file.endswith(".py") and file != "nitrostudio.py":
                    path = os.path.join(root, file)
                    normalized_path = path.replace(os.sep, "/")
                    if normalized_path.startswith("./"):
                        normalized_path = normalized_path[2:]
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read(2048)
                            if "import nitrostack" in content or "from nitrostack" in content or "@mcp_app" in content or "@module" in content:
                                detected.append(normalized_path)
                    except Exception:
                        pass
    except Exception as e:
        push_log(f"SYSTEM: Error scanning projects: {e}")
    return JSONResponse({"projects": detected})


STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.normpath(os.path.join(STUDIO_DIR, "static"))

async def get_index(request):
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h3>NitroStudio static frontend directory is not created yet.</h3>")


# Lifespan context manager for startup tasks
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Start log broadcaster
    asyncio.create_task(broadcast_logs())
    yield

# App routing definitions using Starlette standard
routes = [
    Route("/api/connect", connect, methods=["POST"]),
    Route("/api/disconnect", disconnect, methods=["POST"]),
    Route("/api/status", get_status, methods=["GET"]),
    Route("/api/detect-projects", detect_projects, methods=["GET"]),
    Route("/api/fs/list", fs_list, methods=["GET"]),
    Route("/api/fs/create", fs_create, methods=["POST"]),
    Route("/api/tools", get_tools, methods=["GET"]),
    Route("/api/resources", get_resources, methods=["GET"]),
    Route("/api/prompts", get_prompts, methods=["GET"]),
    Route("/api/call-tool", call_tool, methods=["POST"]),
    Route("/api/read-resource", read_resource, methods=["POST"]),
    Route("/api/get-prompt", get_prompt, methods=["POST"]),
    Route("/api/chat", chat, methods=["POST"]),
    WebSocketRoute("/ws/logs", websocket_logs),
    Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
    Route("/", get_index, methods=["GET"]),
]

app = Starlette(routes=routes, lifespan=lifespan)


def find_free_port(start_port: int = 8000) -> int:
    import socket
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except socket.error:
                port += 1

def start_server(port: int = 8000) -> None:
    resolved_port = find_free_port(port)
    url = f"http://localhost:{resolved_port}"
    print(f"Starting NitroStudio Python Dashboard at {url}...", file=sys.stderr)
    
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(url)
        
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run(app, host="127.0.0.1", port=resolved_port, log_level="warning")


def start_server_cli() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="NitroStudio — Visual dashboard for NitroStack MCP servers")
    parser.add_argument("--port", type=int, default=8000, help="Port to run NitroStudio on")
    args = parser.parse_args()
    start_server(port=args.port)


if __name__ == "__main__":
    start_server_cli()
