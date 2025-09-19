from channels.generic.websocket import AsyncWebsocketConsumer
import json

class InventoryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("inventory_updates", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        print("WebSocket disconnected:", close_code)

    async def send_update(self, event):
        await self.send(json.dumps({
            "message": event["message"]
        }))
