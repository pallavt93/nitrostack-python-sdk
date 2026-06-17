from mcp.server.lowlevel.server import Server
import mcp.types as types

server = Server("test")

async def my_handler(notification):
    print("Handshake completed!")

server.notification_handlers[types.InitializedNotification] = my_handler

print("Registered notification handlers:")
for k, v in server.notification_handlers.items():
    print(k, v)
