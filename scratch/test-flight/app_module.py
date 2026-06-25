from nitrostack import module
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
