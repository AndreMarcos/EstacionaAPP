import asyncio
import aio_pika
import os
from dotenv import load_dotenv
from app.rabbitmq import process_event

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME")
QUEUE_NAME = os.getenv("QUEUE_NAME")

async def main():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    
    exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key="irregularidade.detectada")

    print("🎧 Aguardando eventos de irregularidades...")
    await queue.consume(process_event)

    # Mantenha o processo rodando
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())