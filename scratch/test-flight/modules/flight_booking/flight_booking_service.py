from nitrostack import injectable

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
