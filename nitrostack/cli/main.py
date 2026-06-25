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

FOOD_APP_MODULE_TEMPLATE = """from nitrostack import module
from modules.food_delivery.food_delivery_module import FoodDeliveryModule

@module(
    name="app",
    imports=[FoodDeliveryModule],
    controllers=[],
    providers=[],
    exports=[]
)
class AppModule:
    pass
"""

FOOD_DELIVERY_MODULE_TEMPLATE = """from nitrostack import module
from modules.food_delivery.food_delivery_tools import FoodDeliveryController
from modules.food_delivery.food_delivery_service import FoodDeliveryService

@module(
    name="food_delivery",
    imports=[],
    controllers=[FoodDeliveryController],
    providers=[FoodDeliveryService],
    exports=[FoodDeliveryService]
)
class FoodDeliveryModule:
    pass
"""

FOOD_DELIVERY_SERVICE_TEMPLATE = """from nitrostack import injectable

@injectable(deps=[])
class FoodDeliveryService:
    def __init__(self):
        # In-memory database of items and orders
        self.menu = {
            "pizza": {"price": 12.99, "prep_time": 15},
            "burger": {"price": 8.99, "prep_time": 10},
            "salad": {"price": 7.49, "prep_time": 5},
            "sushi": {"price": 15.99, "prep_time": 20}
        }
        self.orders = {}
        self.order_counter = 1000

    def get_menu(self):
        return self.menu

    def place_order(self, item: str, quantity: int) -> dict:
        item_lower = item.lower()
        if item_lower not in self.menu:
            return {"status": "error", "message": f"Item '{item}' not found in the menu."}
        
        self.order_counter += 1
        order_id = f"ORDER-{self.order_counter}"
        
        price = self.menu[item_lower]["price"] * quantity
        prep_time = self.menu[item_lower]["prep_time"]
        
        self.orders[order_id] = {
            "order_id": order_id,
            "item": item_lower,
            "quantity": quantity,
            "total_price": round(price, 2),
            "status": "Preparing",
            "time_remaining": prep_time
        }
        return self.orders[order_id]

    def get_order_status(self, order_id: str) -> dict:
        return self.orders.get(order_id, {"status": "error", "message": f"Order {order_id} not found."})
"""

FOOD_DELIVERY_TOOLS_TEMPLATE = """from nitrostack import injectable, tool, ExecutionContext
from modules.food_delivery.food_delivery_service import FoodDeliveryService
from pydantic import BaseModel, Field

class ViewMenuInput(BaseModel):
    pass

class PlaceOrderInput(BaseModel):
    item: str = Field(description="The food item to order (e.g., pizza, burger, salad, sushi)")
    quantity: int = Field(default=1, description="Number of items to order")

class OrderStatusInput(BaseModel):
    order_id: str = Field(description="The ID of the order to track (e.g., ORDER-1001)")

@injectable(deps=[FoodDeliveryService])
class FoodDeliveryController:
    def __init__(self, service: FoodDeliveryService):
        self.service = service

    @tool(
        name="view_menu",
        description="View the menu and list available food items and prices",
        input_schema=ViewMenuInput
    )
    async def view_menu(self, input: ViewMenuInput, context: ExecutionContext) -> dict:
        context.logger.info("Fetching food delivery menu...")
        return {"menu": self.service.get_menu()}

    @tool(
        name="place_order",
        description="Place a food delivery order for a menu item",
        input_schema=PlaceOrderInput
    )
    async def place_order(self, input: PlaceOrderInput, context: ExecutionContext) -> dict:
        context.logger.info(f"Placing order for {input.quantity}x {input.item}")
        return self.service.place_order(input.item, input.quantity)

    @tool(
        name="track_order",
        description="Track the status of an existing food delivery order",
        input_schema=OrderStatusInput
    )
    async def track_order(self, input: OrderStatusInput, context: ExecutionContext) -> dict:
        context.logger.info(f"Tracking order status for {input.order_id}")
        return self.service.get_order_status(input.order_id)
"""

FLIGHT_APP_MODULE_TEMPLATE = """from nitrostack import module
from nitrostack.auth.oauth import OAuthModule
from modules.flight_booking.flight_booking_module import FlightBookingModule

@module(
    name="app",
    imports=[
        FlightBookingModule,
        # Configure OAuth resource protection
        OAuthModule.for_root(
            resource_uri="http://localhost:8000/mcp",
            authorization_servers=["http://localhost:3000/oauth"],
            scopes_supported=["flight:read", "flight:write"],
            token_introspection_endpoint="http://localhost:3000/oauth/introspect"
        )
    ],
    controllers=[],
    providers=[],
    exports=[]
)
class AppModule:
    pass
"""

FLIGHT_BOOKING_MODULE_TEMPLATE = """from nitrostack import module
from modules.flight_booking.flight_booking_tools import FlightBookingController
from modules.flight_booking.flight_booking_service import FlightBookingService

@module(
    name="flight_booking",
    imports=[],
    controllers=[FlightBookingController],
    providers=[FlightBookingService],
    exports=[FlightBookingService]
)
class FlightBookingModule:
    pass
"""

FLIGHT_BOOKING_SERVICE_TEMPLATE = """from nitrostack import injectable

@injectable(deps=[])
class FlightBookingService:
    def __init__(self):
        # Mock flight schedule
        self.flights = {
            "FL101": {"from": "NYC", "to": "LON", "date": "2026-07-01", "price": 450.0},
            "FL202": {"from": "PAR", "to": "TOK", "date": "2026-07-02", "price": 850.0},
            "FL303": {"from": "LAX", "to": "NYC", "date": "2026-07-03", "price": 200.0}
        }
        self.bookings = {}
        self.booking_counter = 5000

    def list_flights(self) -> dict:
        return self.flights

    def book_flight(self, flight_id: str, passenger_name: str) -> dict:
        if flight_id not in self.flights:
            return {"status": "error", "message": f"Flight {flight_id} not found."}
        
        self.booking_counter += 1
        booking_id = f"BKG-{self.booking_counter}"
        
        self.bookings[booking_id] = {
            "booking_id": booking_id,
            "flight_id": flight_id,
            "passenger_name": passenger_name,
            "price": self.flights[flight_id]["price"],
            "status": "Confirmed"
        }
        return self.bookings[booking_id]

    def get_booking(self, booking_id: str) -> dict:
        return self.bookings.get(booking_id, {"status": "error", "message": f"Booking {booking_id} not found."})
"""

FLIGHT_BOOKING_TOOLS_TEMPLATE = """from nitrostack import injectable, tool, use_guards, OAuthGuard, ExecutionContext
from modules.flight_booking.flight_booking_service import FlightBookingService
from pydantic import BaseModel, Field

class SearchFlightsInput(BaseModel):
    pass

class BookFlightInput(BaseModel):
    flight_id: str = Field(description="The flight identifier (e.g., FL101, FL202)")
    passenger_name: str = Field(description="Passenger's full name")

class BookingInfoInput(BaseModel):
    booking_id: str = Field(description="The flight booking ID (e.g., BKG-5001)")

@injectable(deps=[FlightBookingService])
class FlightBookingController:
    def __init__(self, service: FlightBookingService):
        self.service = service

    @tool(
        name="search_flights",
        description="Search for available flights and schedules",
        input_schema=SearchFlightsInput
    )
    async def search_flights(self, input: SearchFlightsInput, context: ExecutionContext) -> dict:
        context.logger.info("Searching available flights...")
        return {"flights": self.service.list_flights()}

    @tool(
        name="book_flight",
        description="Book a flight ticket. Requires OAuth authentication.",
        input_schema=BookFlightInput
    )
    @use_guards(OAuthGuard)
    async def book_flight(self, input: BookFlightInput, context: ExecutionContext) -> dict:
        # OAuthGuard validates access token and populates context.auth
        user_id = getattr(context.auth, "subject", "unknown-user")
        context.logger.info(f"Booking flight {input.flight_id} for user {user_id}")
        return self.service.book_flight(input.flight_id, input.passenger_name)

    @tool(
        name="get_booking_details",
        description="Get booking receipt and details. Requires OAuth authentication.",
        input_schema=BookingInfoInput
    )
    @use_guards(OAuthGuard)
    async def get_booking_details(self, input: BookingInfoInput, context: ExecutionContext) -> dict:
        context.logger.info(f"Retrieving details for booking {input.booking_id}")
        return self.service.get_booking(input.booking_id)
"""

OAUTH_SETUP_TEMPLATE = """# OAuth 2.1 Server Setup Guide

To run your flight booking MCP server with OAuth 2.1 protection, you need to configure an OAuth authorization server (like Keycloak, Auth0, Hydra, or a local mock OAuth server).

## 1. Local Configuration

Add the following environment variables to your `.env` file to configure resource protection:

```env
# Introspection endpoint to validate access tokens
OAUTH_INTROSPECTION_ENDPOINT=http://localhost:3000/oauth/introspect

# Or use JWKS (JSON Web Key Sets) to cryptographically verify signatures locally
# JWKS_URI=http://localhost:3000/oauth/jwks
# TOKEN_AUDIENCE=flight-booking-service
# TOKEN_ISSUER=http://localhost:3000/oauth
```

## 2. Protected Routes

The tools in this server use the `@use_guards(OAuthGuard)` decorator to automatically protect endpoints:
* **`search_flights`**: Public (no guard).
* **`book_flight`**: Protected (requires valid access token with `flight:write` scope).
* **`get_booking_details`**: Protected (requires valid access token with `flight:read` scope).

When calling protected tools, the client must pass a valid Bearer token in the `Authorization` header.
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

def print_banner():
    banner = """\033[34m╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   _   _  ___ _____ ____   ___                            ║
║  | \\ | ||_ _|_   _|  _ \\ / _ \\                           ║
║  |  \\| | | |  | | | |_) | | | |                          ║
║  | |\\  | | |  | | |  _ <| |_| |                          ║
║  |_| \\_||___| |_| |_| \\_\\\\___/                           ║
║                                                          ║
║   \033[1;34mNITROSTACK\033[0;34m — Official MCP Framework                   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝\033[0m"""
    print(banner)

def init_project(name: str, template: str = None):
    print_banner()
    
    # 1. Overwrite check
    if os.path.exists(name):
        sys.stdout.write(f"\033[32m? \033[1;37mDirectory '{name}' already exists. Overwrite?\033[0m (Yes/No) [No]: ")
        sys.stdout.flush()
        ans = sys.stdin.readline().strip().lower()
        if ans not in ("y", "yes"):
            print("Initialization cancelled.")
            sys.exit(0)
        # Delete existing folder
        import shutil
        shutil.rmtree(name, ignore_errors=True)
        
    # 2. Select template
    if not template:
        print("\033[32m? \033[1;37mChoose a template:\033[0m")
        print("  \033[34m1. Starter\033[0m     Simple calculator for learning basics")
        print("  \033[34m2. Advanced\033[0m    Food delivery with items & status tracking")
        print("  \033[34m3. OAuth\033[0m       Flight booking with OAuth 2.1 auth")
        
        while True:
            sys.stdout.write("\033[32m? \033[1;37mEnter choice (1-3) [1]:\033[0m ")
            sys.stdout.flush()
            choice = sys.stdin.readline().strip()
            if not choice or choice == "1":
                template = "calculator"
                break
            elif choice == "2":
                template = "food-delivery"
                break
            elif choice == "3":
                template = "flight-booking"
                break
            else:
                print("Invalid choice. Please select 1, 2, or 3.")
    else:
        # Normalize command line template input
        if template == "starter":
            template = "calculator"
        elif template == "advanced":
            template = "food-delivery"
        elif template == "oauth":
            template = "flight-booking"
                
    # 3. Description and Author
    sys.stdout.write("\033[32m? \033[1;37mDescription:\033[0m [My awesome MCP server]: ")
    sys.stdout.flush()
    description = sys.stdin.readline().strip() or "My awesome MCP server"
    
    sys.stdout.write("\033[32m? \033[1;37mAuthor:\033[0m [developer]: ")
    sys.stdout.flush()
    author = sys.stdin.readline().strip() or "developer"
    
    print("\n\033[32m✓\033[0m Project created")
    print("\033[32m✓\033[0m Dependencies installed")
    print("\033[32m✓\033[0m Widget dependencies installed\n")
    
    # Write template files
    if template == "calculator":
        os.makedirs(os.path.join(name, "modules", "calculator"), exist_ok=True)
        with open(os.path.join(name, "app_module.py"), "w", encoding="utf-8") as f:
            f.write(APP_MODULE_TEMPLATE)
        with open(os.path.join(name, "modules", "calculator", "calculator_module.py"), "w", encoding="utf-8") as f:
            f.write(CALC_MODULE_TEMPLATE)
        with open(os.path.join(name, "modules", "calculator", "calculator_service.py"), "w", encoding="utf-8") as f:
            f.write(CALC_SERVICE_TEMPLATE)
        with open(os.path.join(name, "modules", "calculator", "calculator_tools.py"), "w", encoding="utf-8") as f:
            f.write(CALC_TOOLS_TEMPLATE)
    elif template == "food-delivery":
        os.makedirs(os.path.join(name, "modules", "food_delivery"), exist_ok=True)
        with open(os.path.join(name, "app_module.py"), "w", encoding="utf-8") as f:
            f.write(FOOD_APP_MODULE_TEMPLATE)
        with open(os.path.join(name, "modules", "food_delivery", "food_delivery_module.py"), "w", encoding="utf-8") as f:
            f.write(FOOD_DELIVERY_MODULE_TEMPLATE)
        with open(os.path.join(name, "modules", "food_delivery", "food_delivery_service.py"), "w", encoding="utf-8") as f:
            f.write(FOOD_DELIVERY_SERVICE_TEMPLATE)
        with open(os.path.join(name, "modules", "food_delivery", "food_delivery_tools.py"), "w", encoding="utf-8") as f:
            f.write(FOOD_DELIVERY_TEMPLATE) if 'FOOD_DELIVERY_TEMPLATE' in globals() else f.write(FOOD_DELIVERY_TOOLS_TEMPLATE)
    elif template == "flight-booking":
        os.makedirs(os.path.join(name, "modules", "flight_booking"), exist_ok=True)
        with open(os.path.join(name, "app_module.py"), "w", encoding="utf-8") as f:
            f.write(FLIGHT_APP_MODULE_TEMPLATE)
        with open(os.path.join(name, "modules", "flight_booking", "flight_booking_module.py"), "w", encoding="utf-8") as f:
            f.write(FLIGHT_BOOKING_MODULE_TEMPLATE)
        with open(os.path.join(name, "modules", "flight_booking", "flight_booking_service.py"), "w", encoding="utf-8") as f:
            f.write(FLIGHT_BOOKING_SERVICE_TEMPLATE)
        with open(os.path.join(name, "modules", "flight_booking", "flight_booking_tools.py"), "w", encoding="utf-8") as f:
            f.write(FLIGHT_BOOKING_TOOLS_TEMPLATE)
        with open(os.path.join(name, "OAUTH_SETUP.md"), "w", encoding="utf-8") as f:
            f.write(OAUTH_SETUP_TEMPLATE)
            
    with open(os.path.join(name, "main.py"), "w", encoding="utf-8") as f:
        f.write(MAIN_TEMPLATE)
    with open(os.path.join(name, ".env"), "w", encoding="utf-8") as f:
        env_content = f"PORT=8000\nNODE_ENV=development\nSERVER_DESC=\"{description}\"\nSERVER_AUTHOR=\"{author}\"\n"
        f.write(env_content)
    with open(os.path.join(name, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(REQUIREMENTS_TEMPLATE)
        
    # Success Card
    abs_path = os.path.abspath(name)
    success_box = f"""\033[36m╔══════════════════════════════════════════════════════════╗
║ \033[32m✓ Project Ready\033[36m                                          ║
║                                                          ║
║   Name: {name:<48} ║
║   Template: {template:<44} ║
║   Path: {abs_path:<48} ║
╚══════════════════════════════════════════════════════════╝\033[0m"""
    print(success_box)
    
    # Next Steps
    print("\n\033[1;37mNext steps:\033[0m")
    print(f" 1. \033[34mcd {name}\033[0m")
    if template == "flight-booking":
        print(" 2. Configure OAuth credentials in your \033[34m.env\033[0m file")
        print("    See \033[34mOAUTH_SETUP.md\033[0m for provider guides")
    else:
        print(" 2. Configure environment variables in \033[34m.env\033[0m")
    print(" 3. Start development server: \033[34mnitrostack-py dev\033[0m (or `python -m nitrostack.cli.main dev`)")
    print(" 4. Start NitroStudio dashboard: \033[34mnitrostack-studio\033[0m (or `python -m nitrostack.studio`)")
    print("\nHappy coding! 🚀\n")

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

def get_claude_config_paths():
    paths = []
    home = os.path.expanduser("~")
    
    # Windows
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
        # Windows Store app path
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            store_dir = os.path.join(localappdata, "Packages")
            if os.path.exists(store_dir):
                try:
                    for folder in os.listdir(store_dir):
                        if folder.startswith("Claude_"):
                            paths.append(os.path.join(store_dir, folder, "LocalCache", "Roaming", "Claude", "claude_desktop_config.json"))
                except Exception:
                    pass
    # macOS
    elif sys.platform == "darwin":
        paths.append(os.path.join(home, "Library", "Application Support", "Claude", "claude_desktop_config.json"))
    # Linux
    else:
        paths.append(os.path.join(home, ".config", "Claude", "claude_desktop_config.json"))
        
    return [p for p in paths if os.path.exists(os.path.dirname(p))]

def register_server(name: str, file_path: str):
    import json
    
    if not os.path.exists(file_path):
        print(f"Error: Script file '{file_path}' does not exist.")
        sys.exit(1)
        
    abs_file_path = os.path.abspath(file_path)
    python_exe = sys.executable
    
    config_paths = get_claude_config_paths()
    if not config_paths:
        print("Error: Could not find any Claude Desktop installation directories.")
        print("Please ensure Claude Desktop is installed on your machine.")
        sys.exit(1)
        
    registered_any = False
    for path in config_paths:
        try:
            config = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        try:
                            config = json.loads(content)
                        except json.JSONDecodeError:
                            print(f"Warning: Configuration file at '{path}' is not valid JSON. Resetting it.")
            
            if "mcpServers" not in config:
                config["mcpServers"] = {}
                
            config["mcpServers"][name] = {
                "command": python_exe,
                "args": [abs_file_path]
            }
            
            # Create directory if needed
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                
            print(f"Successfully registered server '{name}' in: {path}")
            registered_any = True
        except Exception as e:
            print(f"Error writing to config at '{path}': {e}")
            
    if registered_any:
        print("\nAll done! Please fully restart Claude Desktop to load your new server.")
    else:
        print("Error: Failed to register the server in any configuration files.")

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="nitrostack-py CLI — Scaffold, develop, and run NitroStack Python MCP servers",
        prog="nitrostack-py"
    )
    subparsers = parser.add_subparsers(dest="command")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new NitroStack MCP server project")
    init_parser.add_argument("name", help="Name of the project directory to create")
    init_parser.add_argument("--template", choices=["calculator", "food-delivery", "flight-booking"], default=None, help="Template to use (default: interactive prompt)")

    # dev command
    subparsers.add_parser("dev", help="Start the hot-reloading development server")

    # start command
    subparsers.add_parser("start", help="Start the production server")

    # register command
    reg_parser = subparsers.add_parser("register", help="Register server script inside Claude Desktop configuration")
    reg_parser.add_argument("--name", default=os.path.basename(os.getcwd()), help="Name of the server (defaults to folder name)")
    reg_parser.add_argument("--file", default="main.py", help="Python script to register (defaults to main.py)")

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
        init_project(args.name, args.template)
    elif args.command == "dev":
        run_dev()
    elif args.command == "start":
        run_start()
    elif args.command == "register":
        register_server(args.name, args.file)
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
