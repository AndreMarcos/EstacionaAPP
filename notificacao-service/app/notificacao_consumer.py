import os
import json
import pika
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

TOPIC_EXCHANGE = 'amq.topic'
ROUTING_KEY_NOTIFICACAO = 'fiscalizacao.multa.#'

# Conexão com RabbitMQ
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
connection  = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
)
channel = connection.channel()

# Fila para receber a CONFIRMAÇÃO do agente
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue
channel.queue_bind(
    exchange=TOPIC_EXCHANGE,
    queue=queue_name,
    routing_key=ROUTING_KEY_NOTIFICACAO
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

channel.basic_consume(queue=queue_name, on_message_callback=on_confirmation_received)
print("🚨 Serviço de Notificação rodando. Aguardando mensagens...")
channel.start_consuming()