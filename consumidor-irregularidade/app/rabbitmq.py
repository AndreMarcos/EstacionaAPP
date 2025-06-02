import aio_pika
import os
import json
from app.supabase_client import supabase

async def process_event(message: aio_pika.IncomingMessage):
    async with message.process():
        payload = json.loads(message.body.decode())
        print("📥 Evento recebido:", payload)

        supabase.table("irregularidades").insert(payload).execute()