from dotenv import load_dotenv
load_dotenv()

import os, json, pika
from supabase_client import supabase
from datetime import datetime, timezone

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
QUEUE_NAME = 'fiscalizacao_consulta'

# Setup RabbitMQ
creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
conn  = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds)
)
ch = conn.channel()
ch.queue_declare(queue=QUEUE_NAME, durable=True)

def check_plate(placa: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        resp = (
            supabase.table("creditos")
                     .select("*")
                     .eq("placa", placa)
                     .gte("expira_em", now_iso)
                     .execute()
        )
    except Exception:
        return {"status": False, "mensagem": "Erro interno ao consultar crédito."}
    return {"status": bool(resp.data), 
            "mensagem": "Veículo regular." if resp.data else "Veículo irregular: Sem crédito ativo."}

def on_request(ch, method, props, body):
    req     = json.loads(body)
    placa   = req.get("placa", "")
    corr_id = props.correlation_id
    reply   = props.reply_to

    print(f"[Fiscal] Consulta placa={placa} (corr_id={corr_id[:8]})")
    resp = check_plate(placa)
    resp["correlation_id"] = corr_id

    if reply and corr_id:
        ch.basic_publish(
            exchange='',
            routing_key=reply,
            properties=pika.BasicProperties(
                content_type='application/json',
                correlation_id=corr_id
            ),
            body=json.dumps(resp)
        )
        print(f"[Fiscal] Resposta enviada para {reply}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consuming():
    """Função pública para iniciar o consumer — agora importável."""
    print(f"[Fiscal] rodando, consumindo '{QUEUE_NAME}'…")
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_request)
    ch.start_consuming()

if __name__ == "__main__":
    start_consuming()