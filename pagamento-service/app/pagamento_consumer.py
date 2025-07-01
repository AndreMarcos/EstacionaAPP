import os
import json
import pika
from dotenv import load_dotenv
from supabase_client import supabase

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

# Publica eventos
def send_event(routing_key, payload, correlation_id):
    channel.basic_publish(
        exchange='',
        routing_key=routing_key,
        properties=pika.BasicProperties(delivery_mode=2, correlation_id=correlation_id),
        body=json.dumps(payload)
    )

# Callback para pedidos de pagamento
def on_payment_request(ch, method, properties, body):
    req         = json.loads(body)
    reply_topic = req.get('reply_to').replace('/', '.')
    corr_id     = req.get("correlation_id")
    placa       = req.get("placa").replace('-', '')
    
    print(f"🛠️ Processando pagamento para placa {req.get('placa')}")

    try:
        horas = req.get("duracao_horas", 1)
        valor_por_hora = 5.00
        
        pagamento_record = {
            "placa": placa,
            "duracao_horas": horas,
            "valor": horas * valor_por_hora,
        }
        
        # --- LÓGICA PRINCIPAL ---
        # 1. Insere o pagamento e recupera o registro inserido
        res = supabase.table("pagamentos").insert(pagamento_record).execute()
        
        # O registro recém-criado está em res.data[0]
        pagamento_criado = res.data[0]
        order_id_gerado = pagamento_criado['order_id']
        
        print(f"🛠️ Pagamento registrado com sucesso. Order ID: {order_id_gerado}")
        
        # 2. Responde ao cliente com o status
        response_event = { "order_id": order_id_gerado, "status": "Success", "correlation_id": corr_id }
        channel.basic_publish(
            exchange='amq.topic',
            routing_key=reply_topic,
            properties=pika.BasicProperties(correlation_id=corr_id),
            body=json.dumps(response_event)
        )
        
        # 3. Dispara evento para o Serviço de Crédito com o order_id gerado
        credit_event = {
            "order_id": order_id_gerado, # <-- USA O ID GERADO PELO BANCO
            "placa": placa,
            "zona":  req.get("zona"),
            "duracao_horas": req.get("duracao_horas"),
            "correlation_id": corr_id
        }
        send_event("queue_credito", credit_event, corr_id)

    except Exception as e:
        print(f"🛠️ ERRO no processamento de pagamento: {e}")

    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

# Loop de consumo
channel.basic_consume(queue="queue_pagamento", on_message_callback=on_payment_request)
print("🛠️ Serviço de Pagamento rodando. Aguardando mensagens...")
channel.start_consuming()
