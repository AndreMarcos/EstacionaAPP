import os
import json
import pika
from supabase_client import supabase
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

# Conexão com RabbitMQ
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
connection  = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
)
channel = connection.channel()

# Declaração de fila
channel.queue_declare(queue="queue_fiscalizacao", durable=True)

# Lógica de negócio: verifica créditos válidos e irregularidades
def check_plate(req):
    placa = req.get("placa")
    now   = datetime.utcnow().isoformat()

    credits = supabase.table("creditos")\
        .select("*")\
        .eq("placa", placa)\
        .gte("expira_em", now)\
        .execute().data

    irregs = supabase.table("irregularidades")\
        .select("*")\
        .eq("placa", placa)\
        .execute().data

    if irregs:
        return {"regular": False, "motivo": irregs[0]["motivo"]}
    if not credits:
        return {"regular": False, "motivo": "sem crédito"}
    return {"regular": True}

# Callback de consulta de placa
def on_query(ch, method, properties, body):
    req     = json.loads(body)
    corr_id = properties.correlation_id or req.get("correlation_id")
    print(f"Consultando placa={req.get('placa')}")

    result = check_plate(req)

    # Responde na fila informada em reply_to
    channel.basic_publish(
        exchange='',
        routing_key=req.get("reply_to"),
        properties=pika.BasicProperties(correlation_id=corr_id),
        body=json.dumps(result)
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Loop de consumo
channel.basic_consume(queue="queue_fiscalizacao", on_message_callback=on_query)
print("🔍 Serviço de Fiscalização rodando. Aguardando mensagens em queue_fiscalizacao...")
channel.start_consuming()