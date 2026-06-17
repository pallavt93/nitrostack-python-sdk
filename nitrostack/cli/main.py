import os
import sys
import argparse
import subprocess
import time

MAIN_TEMPLATE = """import asyncio
from nitrostack import McpApplicationFactory
from app_module import AppModule

async def main():
    app = await McpApplicationFactory.create(AppModule)
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())
"""

APP_MODULE_TEMPLATE = """from nitrostack import module
from modules.calculator.calculator_module import CalculatorModule

@module(
    name="app",
    imports=[CalculatorModule],
    controllers=[],
    providers=[],
    exports=[]
)
class AppModule:
    pass
"""

CALC_MODULE_TEMPLATE = """from nitrostack import module
from modules.calculator.calculator_tools import CalculatorController
from modules.calculator.calculator_service import CalculatorService

@module(
    name="calculator",
    imports=[],
    controllers=[CalculatorController],
    providers=[CalculatorService],
    exports=[CalculatorService]
)
class CalculatorModule:
    pass
"""

CALC_SERVICE_TEMPLATE = """from nitrostack import injectable

@injectable(deps=[])
class CalculatorService:
    def add(self, a: float, b: float) -> float:
        return a + b
"""

CALC_TOOLS_TEMPLATE = """from nitrostack import injectable, tool, ExecutionContext
from modules.calculator.calculator_service import CalculatorService
from pydantic import BaseModel

class AddInput(BaseModel):
    a: float
    b: float

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
"""

ENV_TEMPLATE = """PORT=8000
NODE_ENV=development
"""

REQUIREMENTS_TEMPLATE = """nitrostack
"""

TOOL_TEMPLATE = """from nitrostack import tool, ExecutionContext
from pydantic import BaseModel

class {camel_name}Input(BaseModel):
    # Add input parameters here
    pass

@tool(
    name="{name}",
    description="Implement your tool description here",
    input_schema={camel_name}Input
)
async def {name}_handler(input: {camel_name}Input, context: ExecutionContext):
    context.logger.info("Executing tool {name}")
    return {{"status": "success"}}
"""

MODULE_TEMPLATE = """from nitrostack import module

@module(
    name="{name}",
    imports=[],
    controllers=[],
    providers=[],
    exports=[]
)
class {camel_name}Module:
    pass
"""

def init_project(name: str):
    if os.path.exists(name):
        print(f"Error: Directory '{name}' already exists.")
        sys.exit(1)
        
    print(f"Creating project '{name}'...")
    os.makedirs(os.path.join(name, "modules", "calculator"), exist_ok=True)
    
    with open(os.path.join(name, "main.py"), "w", encoding="utf-8") as f:
        f.write(MAIN_TEMPLATE)
    with open(os.path.join(name, "app_module.py"), "w", encoding="utf-8") as f:
        f.write(APP_MODULE_TEMPLATE)
    with open(os.path.join(name, "modules", "calculator", "calculator_module.py"), "w", encoding="utf-8") as f:
        f.write(CALC_MODULE_TEMPLATE)
    with open(os.path.join(name, "modules", "calculator", "calculator_service.py"), "w", encoding="utf-8") as f:
        f.write(CALC_SERVICE_TEMPLATE)
    with open(os.path.join(name, "modules", "calculator", "calculator_tools.py"), "w", encoding="utf-8") as f:
        f.write(CALC_TOOLS_TEMPLATE)
    with open(os.path.join(name, ".env"), "w", encoding="utf-8") as f:
        f.write(ENV_TEMPLATE)
    with open(os.path.join(name, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(REQUIREMENTS_TEMPLATE)
        
    print(f"Project '{name}' successfully initialized!")

def run_dev():
    target = "main.py"
    if not os.path.exists(target):
        print("Error: main.py not found in current directory.")
        sys.exit(1)
        
    print(f"Starting hot-reload development server for {target}...")
    process = None
    
    def start_process():
        nonlocal process
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(".")
        process = subprocess.Popen([sys.executable, target], env=env)

    start_process()
    
    watched_extensions = {".py", ".env"}
    
    def get_mtimes():
        mtimes = {}
        for root, dirs, files in os.walk("."):
            if any(part.startswith(".") or part in ("venv", "env", "__pycache__") for part in root.split(os.sep)):
                continue
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in watched_extensions:
                    path = os.path.join(root, file)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except Exception:
                        pass
        return mtimes

    # Try using watchfiles for high-performance, low-CPU file monitoring
    try:
        from watchfiles import watch
        print("Using watchfiles for high-performance file monitoring.")
        
        # Check if process is running and restart if needed
        while True:
            # We watch files blockingly. watch() yields when changes happen.
            for changes in watch("."):
                should_restart = False
                for change_type, path in changes:
                    ext = os.path.splitext(path)[1]
                    if ext in watched_extensions:
                        # Ignore standard hidden or package environment folders
                        parts = os.path.normpath(path).split(os.sep)
                        if not any(p in parts for p in ("venv", "env", "__pycache__", ".git", ".pytest_cache", "nitrostack.egg-info")):
                            should_restart = True
                            break
                if should_restart:
                    print("File changes detected! Restarting server...")
                    start_process()
            
            # Fallback sleep if loop exits
            time.sleep(0.5)
            if process and process.poll() is not None:
                print("Server process exited. Waiting for file changes to restart...")
                
    except ImportError:
        print("watchfiles library not found. Falling back to standard polling...")
        last_mtimes = get_mtimes()
        try:
            while True:
                time.sleep(1)
                if process and process.poll() is not None:
                    print("Server process exited. Waiting for file changes to restart...")
                current_mtimes = get_mtimes()
                changed = False
                if set(current_mtimes.keys()) != set(last_mtimes.keys()):
                    changed = True
                else:
                    for path, mtime in current_mtimes.items():
                        if last_mtimes.get(path) != mtime:
                            changed = True
                            break
                if changed:
                    print("File changes detected! Restarting server...")
                    start_process()
                    last_mtimes = current_mtimes
        except KeyboardInterrupt:
            pass
    except KeyboardInterrupt:
        print("\nStopping development server...")
        if process:
            try:
                process.terminate()
            except Exception:
                pass

def run_start():
    target = "main.py"
    if not os.path.exists(target):
        print("Error: main.py not found in current directory.")
        sys.exit(1)
    
    print(f"Starting production server for {target}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(".")
    try:
        subprocess.run([sys.executable, target], env=env)
    except KeyboardInterrupt:
        print("\nStopping server...")

def generate_tool(name: str):
    filename = f"{name}_tool.py"
    if os.path.exists(filename):
        print(f"Error: File '{filename}' already exists.")
        sys.exit(1)
    camel_name = "".join(part.capitalize() for part in name.split("_"))
    content = TOOL_TEMPLATE.format(name=name, camel_name=camel_name)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated tool boilerplate in '{filename}'")

def generate_module(name: str):
    filename = f"{name}_module.py"
    if os.path.exists(filename):
        print(f"Error: File '{filename}' already exists.")
        sys.exit(1)
    camel_name = "".join(part.capitalize() for part in name.split("_"))
    content = MODULE_TEMPLATE.format(name=name, camel_name=camel_name)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated module boilerplate in '{filename}'")

def main():
    parser = argparse.ArgumentParser(
        description="nitrostack-py CLI — Scaffold, develop, and run NitroStack Python MCP servers",
        prog="nitrostack-py"
    )
    subparsers = parser.add_subparsers(dest="command")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new NitroStack MCP server project")
    init_parser.add_argument("name", help="Name of the project directory to create")

    # dev command
    subparsers.add_parser("dev", help="Start the hot-reloading development server")

    # start command
    subparsers.add_parser("start", help="Start the production server")

    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate boilerplate code")
    gen_subparsers = gen_parser.add_subparsers(dest="generator")
    
    tool_parser = gen_subparsers.add_parser("tool", help="Generate a new tool boilerplate")
    tool_parser.add_argument("name", help="Name of the tool")

    mod_parser = gen_subparsers.add_parser("module", help="Generate a new module boilerplate")
    mod_parser.add_argument("name", help="Name of the module")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init":
        init_project(args.name)
    elif args.command == "dev":
        run_dev()
    elif args.command == "start":
        run_start()
    elif args.command == "generate":
        if not args.generator:
            parser.parse_args(["generate", "--help"])
            sys.exit(1)
        if args.generator == "tool":
            generate_tool(args.name)
        elif args.generator == "module":
            generate_module(args.name)

if __name__ == "__main__":
    main()
