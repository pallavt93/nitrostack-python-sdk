from nitrostack import injectable, tool, use_guards, OAuthGuard, ExecutionContext
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
