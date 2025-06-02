import aio_pika
import asyncio
import os

exchange_name = os.getenv("EXCHANGE_NAME")

class RabbitPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL"))
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(exchange_name, aio_pika.ExchangeType.TOPIC, durable=True)

    async def publish_event(self, routing_key: str, message: dict):
        import json
        await self.exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key=routing_key,
        )

publisher = RabbitPublisher()

async def init_rabbitmq():
    await publisher.connect()