# Flight Booking MCP Server Example (with OAuth 2.1)
#
# This example demonstrates how to protect MCP tools using OAuth 2.1.
# The tools 'book_flight' and 'get_booking_details' are protected by the @use_guards(OAuthGuard)
# decorator, requiring a valid OAuth token from the configured introspection endpoint or JWKS provider.
#
# To run this example, configure the OAuth settings in your .env file:
#   PORT=8000
#   OAUTH_INTROSPECTION_ENDPOINT=http://localhost:3000/oauth/introspect
#   # Or using JWKS:
#   # JWKS_URI=http://localhost:3000/oauth/jwks
#   # TOKEN_AUDIENCE=flight-booking-service
#   # TOKEN_ISSUER=http://localhost:3000/oauth

import asyncio
import os
import sys
from typing import Dict, Any, List
from pydantic import BaseModel, Field

# Ensure parent directory is in sys.path so nitrostack can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nitrostack import (
    tool,
    injectable,
    module,
    mcp_app,
    McpApplicationFactory,
    ServerConfig,
    ExecutionContext,
    use_guards,
    OAuthGuard,
)
from nitrostack.auth.oauth import OAuthModule

# 1. Input Validation Schemas
class SearchFlightsInput(BaseModel):
    pass

class BookFlightInput(BaseModel):
    flight_id: str = Field(description="The flight identifier (e.g., FL101, FL202, FL303)")
    passenger_name: str = Field(description="Passenger's full name")

class BookingInfoInput(BaseModel):
    booking_id: str = Field(description="The flight booking ID (e.g., BKG-5001)")


# 2. Flight Booking Business Service
@injectable(deps=[])
class FlightBookingService:
    def __init__(self):
        # Mock flight schedules
        self.flights = {
            "FL101": {"from": "NYC", "to": "LON", "date": "2026-07-01", "price": 450.0},
            "FL202": {"from": "PAR", "to": "TOK", "date": "2026-07-02", "price": 850.0},
            "FL303": {"from": "LAX", "to": "NYC", "date": "2026-07-03", "price": 200.0}
        }
        self.bookings = {}
        self.booking_counter = 5000

    def list_flights(self) -> Dict[str, Any]:
        return self.flights

    def book_flight(self, flight_id: str, passenger_name: str) -> Dict[str, Any]:
        if flight_id not in self.flights:
            raise ValueError(f"Flight {flight_id} not found.")
        
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

    def get_booking(self, booking_id: str) -> Dict[str, Any]:
        if booking_id not in self.bookings:
            raise KeyError(f"Booking {booking_id} not found.")
        return self.bookings[booking_id]


# 3. Controller exposing tools with OAuth Guards
@injectable(deps=[FlightBookingService])
class FlightBookingController:
    def __init__(self, service: FlightBookingService):
        self.service = service

    @tool(
        name="search_flights",
        title="Search Flights",
        description="Search for available flights and schedules (No Auth required)",
        input_schema=SearchFlightsInput
    )
    async def search_flights(self, input: SearchFlightsInput, context: ExecutionContext) -> Dict[str, Any]:
        context.logger.info("Searching available flights...")
        return {"flights": self.service.list_flights()}

    @tool(
        name="book_flight",
        title="Book Flight Ticket",
        description="Book a flight ticket. Requires OAuth authentication.",
        input_schema=BookFlightInput
    )
    @use_guards(OAuthGuard)
    async def book_flight(self, input: BookFlightInput, context: ExecutionContext) -> Dict[str, Any]:
        # OAuthGuard validates access token and populates context.auth
        user_id = getattr(context.auth, "subject", "unknown-user")
        context.logger.info(f"Booking flight {input.flight_id} for user {user_id}")
        try:
            result = self.service.book_flight(input.flight_id, input.passenger_name)
            return {"status": "success", "booking": result}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    @tool(
        name="get_booking_details",
        title="Get Booking Details",
        description="Get booking receipt and details. Requires OAuth authentication.",
        input_schema=BookingInfoInput
    )
    @use_guards(OAuthGuard)
    async def get_booking_details(self, input: BookingInfoInput, context: ExecutionContext) -> Dict[str, Any]:
        context.logger.info(f"Retrieving details for booking {input.booking_id}")
        try:
            result = self.service.get_booking(input.booking_id)
            return {"status": "success", "booking": result}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


# 4. Modules
@module(
    name="flight_booking",
    controllers=[FlightBookingController],
    providers=[FlightBookingService],
    exports=[FlightBookingService]
)
class FlightBookingModule:
    pass

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
    ]
)
class AppModule:
    pass


# 5. Application Entrypoint
@mcp_app(
    module=AppModule,
    server=ServerConfig(name="flight-booking-server", version="1.0.0")
)
class App:
    pass

async def main():
    sys.stderr.write("Starting Flight Booking Server...\n")
    sys.stderr.flush()
    app = await McpApplicationFactory.create(App)
    await app.start()

if __name__ == "__main__":
    asyncio.run(main())
