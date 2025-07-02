import os
import json
import pika
from supabase_client import supabase
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

TOPIC_EXCHANGE = 'amq.topic'
ROUTING_KEY_FISCALIZACAO = 'fiscalizacao.consulta.#'
QUEUE_NAME = 'queue_fiscalizacao'

# Conexão com RabbitMQ
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
connection  = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
)
channel = connection.channel()

# Declaração da fila de fiscalização
channel.queue_declare(queue=QUEUE_NAME, durable=True)
channel.queue_bind(
    exchange=TOPIC_EXCHANGE,
    queue=QUEUE_NAME,
    routing_key=ROUTING_KEY_FISCALIZACAO
)

# Lógica de negócio: verifica créditos válidos
def check_plate(req):
    placa = req.get("placa")
    now   = datetime.now(timezone.utc).isoformat()

    try:
        credits = supabase.table("creditos")\
            .select("*")\
            .eq("placa", placa)\
            .gte("expira_em", now)\
            .execute().data
    except Exception as e:
        print(f"🔍 ERRO ao consultar Supabase: {e}")
        return {"status": False, "mensagem": "Erro interno ao consultar crédito."}

    if not credits:
        # --- VEÍCULO IRREGULAR ---
        # Apenas prepara uma resposta informando a irregularidade.
        print(f"🔍 Veículo {placa} irregular.")
        return {
            "status": False,
            "mensagem": "Veículo irregular: Sem crédito ativo."
        }
    
    print(f"🔍 Veículo {placa} está regular.")
    return {"status": True, "mensagem": "Veículo regular."}

# Callback de consulta de placa
def on_query(ch, method, properties, body):
    try:
        req         = json.loads(body)
        reply_to    = req.get('reply_to').replace('/', '.')
        corr_id     = properties.correlation_id or req.get("correlation_id")
        
        print(f"🔍 Consultando placa={req.get('placa')}")

        result = check_plate(req)
        result['correlation_id'] = corr_id
        
        # Responde ao solicitante original (App do Agente)
        if reply_to:
            print(f"🔍 Respondendo na fila '{reply_to}'")
            channel.basic_publish(
                exchange='amq.topic',
                routing_key=reply_to,
                properties=pika.BasicProperties(correlation_id=corr_id),
                body=json.dumps(result)
            )
    except Exception as e:
        print(f"🔍 ERRO GERAL: {str(e)}")
    finally:    
        ch.basic_ack(delivery_tag=method.delivery_tag)

# Loop de consumo
channel.basic_consume(queue="queue_fiscalizacao", on_message_callback=on_query)
print("🔍 Serviço de Fiscalização rodando. Aguardando mensagens...")
channel.start_consuming()