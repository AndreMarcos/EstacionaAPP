import pika
import json
import os
from supabase_client import supabase
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials))
channel = connection.channel()

channel.queue_declare(queue="auth_signup", durable=True)
channel.queue_declare(queue="auth_login", durable=True)
channel.queue_declare(queue="auth_response", durable=True)


def send_response(correlation_id, response):
    channel.basic_publish(
        exchange='',
        routing_key='auth_response',
        properties=pika.BasicProperties(correlation_id=correlation_id),
        body=json.dumps(response)
    )
    print(f"Resposta enviada: {response}")

def process_signup(data):
    email = data['email']
    password = data['password']
    response = supabase.auth.sign_up({"email": email, "password": password})
    if response.get("error"):
        return {"success": False, "error": response["error"]["message"]}
    else:
        return {"success": True, "message": "Usuário criado com sucesso."}

def process_login(data):
    email = data['email']
    password = data['password']
    response = supabase.auth.sign_in(email=email, password=password)
    if response.get("error"):
        return {"success": False, "error": response["error"]["message"]}
    else:
        return {
            "success": True,
            "access_token": response["access_token"],
            "refresh_token": response["refresh_token"]
        }

def on_signup(ch, method, properties, body):
    data = json.loads(body)
    correlation_id = data.get("correlation_id")
    print(f"Processando signup para {data['email']}")
    response = process_signup(data)
    send_response(correlation_id, response)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def on_login(ch, method, properties, body):
    data = json.loads(body)
    correlation_id = data.get("correlation_id")
    print(f"Processando login para {data['email']}")
    response = process_login(data)
    send_response(correlation_id, response)
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consuming():
    channel.basic_consume(queue="auth_signup", on_message_callback=on_signup)
    channel.basic_consume(queue="auth_login", on_message_callback=on_login)

    print("👤 Auth Service rodando. Aguardando mensagens...")
    channel.start_consuming()
    