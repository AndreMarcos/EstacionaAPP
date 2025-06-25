import os
import json
import pika
from supabase_client import supabase
from dotenv import load_dotenv

load_dotenv()

# RabbitMQ
HOST = os.getenv("RABBITMQ_HOST")
USER = os.getenv("RABBITMQ_USER")
PASS = os.getenv("RABBITMQ_PASS")
credentials = pika.PlainCredentials(USER, PASS)
connection = pika.BlockingConnection(pika.ConnectionParameters(host=HOST, credentials=credentials))
channel = connection.channel()

# Filas
channel.queue_declare(queue="vehicle_register", durable=True)
channel.queue_declare(queue="vehicle_list", durable=True)
channel.queue_declare(queue="vehicle_response", durable=True)

def send_response(corr_id, payload):
    channel.basic_publish(
        exchange='',
        routing_key='vehicle_response',
        properties=pika.BasicProperties(correlation_id=corr_id),
        body=json.dumps(payload)
    )

def process_register(data):
    """Insere um novo veículo e retorna o ID."""
    record = {
        "user_id": data["user_id"],
        "placa": data["placa"],
        "modelo": data.get("modelo"),
        "cor": data.get("cor")
    }
    res = supabase.table("veiculos").insert(record).execute()
    if res.error:
        return {"success": False, "error": res.error.message}
    vehicle = res.data[0]
    return {"success": True, "message": "Veículo cadastrado", "vehicle_id": vehicle["id"]}

def process_list(data):
    """Retorna a lista de veículos do usuário."""
    user_id = data["user_id"]
    res = supabase.table("veiculos").select("*").eq("user_id", user_id).execute()
    if res.error:
        return {"success": False, "error": res.error.message}
    return {"success": True, "veiculos": res.data}

def on_register(ch, method, props, body):
    msg = json.loads(body)
    corr_id = msg.get("correlation_id")
    print("Cadastrando veículo:", msg)
    response = process_register(msg)
    response["correlation_id"] = corr_id
    send_response(corr_id, response)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def on_list(ch, method, props, body):
    msg = json.loads(body)
    corr_id = msg.get("correlation_id")
    print("Listando veículos para user:", msg.get("user_id"))
    response = process_list(msg)
    response["correlation_id"] = corr_id
    send_response(corr_id, response)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consuming():
    channel.basic_consume(queue="vehicle_register", on_message_callback=on_register)
    channel.basic_consume(queue="vehicle_list", on_message_callback=on_list)
    print("🚗 Service de Veículos rodando. Aguardando mensagens...")
    channel.start_consuming()