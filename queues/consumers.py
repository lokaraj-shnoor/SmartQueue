import json

from channels.generic.websocket import AsyncWebsocketConsumer


class QueueConsumer(AsyncWebsocketConsumer):
    group_name = "live_queue"

    async def connect(self):
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "event": event["event"],
                    "payload": event["payload"],
                }
            )
        )
