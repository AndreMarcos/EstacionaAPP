import os
import json
import pika
from dotenv import load_dotenv

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

# Fila para receber a CONFIRMAÇÃO do agente
QUEUE_NAME = 'queue_notificacao'
channel.queue_declare(queue=QUEUE_NAME, durable=True)
channel.queue_bind(
    exchange='amq.topic',
    queue=QUEUE_NAME,
    routing_key=QUEUE_NAME
)

print('[*] Aguardando CONFIRMAÇÃO de multa do agente. Para sair, pressione CTRL+C')

def on_confirmation_received(ch, method, properties, body):
    """Callback para processar a confirmação de multa vinda do agente."""
    data = json.loads(body)
    placa = data.get('placa')
    localizacao = data.get('localizacao', 'N/A')

    print(f"\n------ 🚨 CONFIRMAÇÃO DE MULTA RECEBIDA 🚨 ------")
    print(f"  [>] Placa: {placa}")
    print(f"  [>] Localização: {localizacao}")
    print(f"  [>] Acionando Guarda Municipal para emissão de multa...")
    print(f"--------------------------------------------------")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_confirmation_received)
print("🚨 Serviço de Notificação rodando. Aguardando mensagens em queue_notificacao...")
channel.start_consuming()