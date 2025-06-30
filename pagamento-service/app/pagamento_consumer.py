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

# Declaração de filas
channel.queue_declare(queue="queue_pagamento",     durable=True)
channel.queue_declare(queue="pagamento_response",  durable=True)
channel.queue_declare(queue="queue_credito",       durable=True)

channel.queue_bind(
    exchange='amq.topic',
    queue='queue_pagamento',
    routing_key='queue_pagamento'
)

# Publica eventos ou respostas mantendo o correlation_id
def send_event(routing_key, payload, correlation_id):
    channel.basic_publish(
        exchange='',
        routing_key=routing_key,
        properties=pika.BasicProperties(
            delivery_mode=2,
            correlation_id=correlation_id
        ),
        body=json.dumps(payload)
    )

# Callback para pedidos de pagamento
def on_payment_request(ch, method, properties, body):
    req         = json.loads(body)
    reply_topic = req.get('reply_to').replace('/', '.')
    corr_id     = req.get("correlation_id")
    
    print(f"🛠 Processando pagamento para 'order_id={req.get('order_id')}'")

    # --- Aqui você integraria com o gateway de pagamento real ---
    event = {
        "order_id": req.get("order_id"),
        "status":   "Success"
    }
    
    event['correlation_id'] = corr_id

    # 1) Responde ao cliente
    channel.basic_publish(
        exchange='amq.topic',
        routing_key=reply_topic,
        properties=pika.BasicProperties(correlation_id=corr_id),
        body=json.dumps(event)
    )
    # 2) Dispara evento para o Serviço de Crédito
    credit_event = {
        **event,
        "placa": req.get("placa"),
        "zona":  req.get("zona"),
        "duracao_horas": req.get("duracao_horas"),
    }
    send_event("queue_credito", credit_event, corr_id)

    ch.basic_ack(delivery_tag=method.delivery_tag)

# Loop de consumo
channel.basic_consume(queue="queue_pagamento", on_message_callback=on_payment_request)
print("🛠 Serviço de Pagamento rodando. Aguardando mensagens em queue_pagamento...")
channel.start_consuming()