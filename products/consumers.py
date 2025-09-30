from channels.generic.websocket import AsyncWebsocketConsumer
import json

class InventoryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("inventory_group", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        print("WebSocket disconnected:", close_code)

    async def product_update(self, event):  # must match "type" in signals
        await self.send(text_data=json.dumps({"message": event["message"]}))


