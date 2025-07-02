import os
import json
import pika
from dotenv import load_dotenv
from supabase_client import supabase

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

TOPIC_EXCHANGE = 'amq.topic'
ROUTING_KEY_PAGAMENTO = 'credito.compra.#'
ROUTING_KEY_SUCCESS = 'credito.confirmacao.sucesso'
QUEUE_NAME = 'queue_pagamento'

# Conexão com RabbitMQ
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
connection  = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
)
channel = connection.channel()

# Declaração de filas
channel.queue_declare(queue=QUEUE_NAME,     durable=True)

channel.queue_bind(
    exchange=TOPIC_EXCHANGE,
    queue=QUEUE_NAME,
    routing_key=ROUTING_KEY_PAGAMENTO
)

# Publica eventos
def send_event(routing_key, payload, correlation_id):
    channel.basic_publish(
        exchange=TOPIC_EXCHANGE,
        routing_key=routing_key,
        properties=pika.BasicProperties(delivery_mode=2, correlation_id=correlation_id),
        body=json.dumps(payload)
    )

# Callback para pedidos de pagamento
def on_payment_request(ch, method, properties, body):
    req         = json.loads(body)
    reply_to    = req.get('reply_to').replace('/', '.')
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
        
        res = supabase.table("pagamentos").insert(pagamento_record).execute()
        pagamento_criado = res.data[0]
        order_id_gerado = pagamento_criado['order_id']
        
        print(f"🛠️ Pagamento registrado com sucesso. Order ID: {order_id_gerado}")
        
        credit_event = {
            "order_id": order_id_gerado,
            "placa": placa,
            "zona":  req.get("zona"),
            "duracao_horas": req.get("duracao_horas"),
            "reply_to": reply_to,
            "correlation_id": corr_id
        }
        send_event(ROUTING_KEY_SUCCESS, credit_event, corr_id)

    except Exception as e:
        print(f"🛠️ ERRO no processamento de pagamento: {e}")
        # --- MUDANÇA 3: Adicionado bloco para responder ao cliente em caso de erro ---
        if reply_to:
            error_response = {"success": False, "error": f"Falha no serviço de pagamento: {e}"}
            channel.basic_publish(
                exchange=TOPIC_EXCHANGE,
                routing_key=reply_to,
                properties=pika.BasicProperties(correlation_id=corr_id),
                body=json.dumps(error_response)
            )

    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consuming():
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_payment_request)
    print("🛠️ Serviço de Pagamento rodando. Aguardando mensagens...")
    channel.start_consuming()
