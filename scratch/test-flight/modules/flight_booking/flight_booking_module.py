from nitrostack import module
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
