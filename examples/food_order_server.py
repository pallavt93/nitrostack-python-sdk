import asyncio
import os
import sys
import uuid
from typing import Literal, Dict, Any, List, Optional
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
)

# 1. Input Schemas using Pydantic
class OrderItem(BaseModel):
    item_name: str = Field(description="Name of the food item (e.g. Pizza, Burger, Salad)")
    quantity: int = Field(default=1, description="Quantity of the item to order")
    notes: Optional[str] = Field(None, description="Special instructions (e.g. No onions, extra cheese)")

class PlaceOrderInput(BaseModel):
    items: List[OrderItem] = Field(description="List of food items and quantities")
    address: str = Field(description="Delivery address")
    payment_method: Literal["cash", "card", "paypal"] = Field(description="Payment method to use")

class CancelOrderInput(BaseModel):
    order_id: str = Field(description="The unique order ID to cancel")
    reason: str = Field(description="Reason for cancellation")


# 2. Food Order Service (Business Logic)
@injectable(deps=[ConfigService])
class FoodOrderService:
    def __init__(self, config: ConfigService):
        self.config = config
        self.tax_rate = float(self.config.get("TAX_RATE", "0.08"))
        self.delivery_fee = float(self.config.get("DELIVERY_FEE", "3.99"))
        
        # In-memory database of menu items
        self.menu = {
            "Pizza Margherita": {"price": 12.99, "diet": ["vegetarian"]},
            "Classic Cheeseburger": {"price": 9.99, "diet": ["none"]},
            "Caesar Salad": {"price": 8.49, "diet": ["vegetarian"]},
            "Vegan Poke Bowl": {"price": 13.50, "diet": ["vegan", "vegetarian", "gluten-free"]},
            "Spicy Tuna Roll": {"price": 14.99, "diet": ["gluten-free"]},
            "Chocolate Lava Cake": {"price": 6.50, "diet": ["vegetarian"]},
        }
        
        # In-memory database of active orders
        self.orders = {}

    def get_menu(self) -> Dict[str, Any]:
        return self.menu

    def place_order(self, items: List[OrderItem], address: str, payment: str) -> Dict[str, Any]:
        subtotal = 0.0
        processed_items = []
        
        for item in items:
            menu_item = self.menu.get(item.item_name)
            if not menu_item:
                raise ValueError(f"Item '{item.item_name}' is not on the menu.")
            
            item_price = menu_item["price"]
            item_total = item_price * item.quantity
            subtotal += item_total
            processed_items.append({
                "item_name": item.item_name,
                "quantity": item.quantity,
                "price": item_price,
                "notes": item.notes,
                "total": round(item_total, 2)
            })
            
        tax = subtotal * self.tax_rate
        total = subtotal + tax + self.delivery_fee
        order_id = f"FOOD-{uuid.uuid4().hex[:6].upper()}"
        
        self.orders[order_id] = {
            "order_id": order_id,
            "items": processed_items,
            "address": address,
            "payment_method": payment,
            "subtotal": round(subtotal, 2),
            "tax": round(tax, 2),
            "delivery_fee": self.delivery_fee,
            "total": round(total, 2),
            "status": "preparing",
            "estimated_delivery_minutes": 35
        }
        
        return self.orders[order_id]

    def cancel_order(self, order_id: str, reason: str) -> bool:
        if order_id not in self.orders:
            raise KeyError(f"Order ID '{order_id}' not found.")
        order = self.orders[order_id]
        if order["status"] in ("out_for_delivery", "delivered"):
            raise ValueError(f"Cannot cancel order {order_id} because it is already {order['status']}.")
        
        order["status"] = "cancelled"
        order["cancellation_reason"] = reason
        return True

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        if order_id not in self.orders:
            raise KeyError(f"Order ID '{order_id}' not found.")
        return self.orders[order_id]


# 3. Controller exposing MCP endpoints
@injectable(deps=[FoodOrderService])
class FoodOrderController:
    def __init__(self, order_service: FoodOrderService):
        self.order_service = order_service

    # MCP Tool: place_order
    @tool(
        name="place_order",
        title="Place Food Order",
        description="Place a new delivery order for items from the menu",
        input_schema=PlaceOrderInput
    )
    async def place_order(self, input: PlaceOrderInput, context: ExecutionContext) -> Dict[str, Any]:
        context.logger.info(f"Placing order to address: {input.address} using {input.payment_method}")
        try:
            order = self.order_service.place_order(input.items, input.address, input.payment_method)
            return {"status": "success", "order": order}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # MCP Tool: cancel_order
    @tool(
        name="cancel_order",
        title="Cancel Order",
        description="Cancel an active food order before it goes out for delivery",
        input_schema=CancelOrderInput
    )
    async def cancel_order(self, input: CancelOrderInput, context: ExecutionContext) -> Dict[str, Any]:
        context.logger.info(f"Cancelling order {input.order_id}. Reason: {input.reason}")
        try:
            self.order_service.cancel_order(input.order_id, input.reason)
            return {"status": "success", "message": f"Order {input.order_id} was successfully cancelled."}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # MCP Resource: food://menu
    @resource(
        uri="food://menu",
        name="Restaurant Menu",
        description="The current restaurant menu with pricing and dietary information",
        mime_type="application/json"
    )
    async def get_menu(self, context: ExecutionContext) -> Dict[str, Any]:
        return self.order_service.get_menu()

    # MCP Resource: food://orders/{order_id}
    @resource(
        uri="food://orders/{order_id}",
        name="Order Tracker",
        description="Track the status of a placed delivery order in real-time",
        mime_type="application/json"
    )
    async def get_order_tracking(self, order_id: str, context: ExecutionContext) -> Dict[str, Any]:
        try:
            return self.order_service.get_order_status(order_id)
        except KeyError:
            return {"error": f"No order found with ID {order_id}"}

    # MCP Prompt: recommend_meal
    @prompt(
        name="recommend_meal",
        description="Suggest menu recommendations based on dietary preferences",
        arguments=[
            PromptArgument(name="diet", description="Dietary preference (vegan, vegetarian, gluten-free, none)", required=True),
            PromptArgument(name="max_price", description="Maximum price limit in USD", required=False)
        ]
    )
    async def recommend_meal(self, args: dict, context: ExecutionContext) -> List[PromptMessage]:
        diet = args.get("diet", "none").lower()
        max_price_str = args.get("max_price")
        max_price = float(max_price_str) if max_price_str else 999.0
        
        menu = self.order_service.get_menu()
        recommendations = []
        
        for name, details in menu.items():
            if details["price"] <= max_price:
                if diet == "none" or diet in details["diet"]:
                    recommendations.append(f"- {name} (${details['price']})")
                    
        if not recommendations:
            rec_text = f"We couldn't find any items matching diet '{diet}' under ${max_price}."
        else:
            rec_text = f"Here are recommendations matching diet '{diet}':\n" + "\n".join(recommendations)
            
        return [
            PromptMessage(role="system", content="You are a helpful restaurant assistant making menu recommendations."),
            PromptMessage(role="user", content=rec_text)
        ]


# 4. Scaffolding Modules
@module(
    name="food_order",
    controllers=[FoodOrderController],
    providers=[FoodOrderService],
    exports=[FoodOrderService]
)
class FoodOrderModule:
    pass

@module(
    name="app",
    imports=[
        FoodOrderModule,
        ConfigModule.for_root(
            env_file_path=".env",
            defaults={"TAX_RATE": "0.08", "DELIVERY_FEE": "3.99"}
        )
    ]
)
class AppModule:
    pass

@mcp_app(
    module=AppModule,
    server=ServerConfig(name="food-delivery-server", version="1.0.0")
)
class App:
    pass


async def main():
    import sys
    sys.stderr.write("Initializing Food Ordering MCP Server...\n")
    sys.stderr.flush()
    app = await McpApplicationFactory.create(App)
    sys.stderr.write("Starting server over stdio...\n")
    sys.stderr.flush()
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())
