import os
import json
import uuid
import pika
from supabase_client import supabase
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
env = os.environ

# --- Consome do mesmo nome de fila que o CLI publica ---
QUEUE_NAME = 'credito_compra'

# Conexão RabbitMQ
creds = pika.PlainCredentials(env["RABBITMQ_USER"], env["RABBITMQ_PASS"])
params = pika.ConnectionParameters(host=env["RABBITMQ_HOST"], credentials=creds)
conn = pika.BlockingConnection(params)
ch = conn.channel()
ch.queue_declare(queue=QUEUE_NAME, durable=True)

def process_purchase(data):
    placa = data["placa"]
    horas = data.get("duracao_horas", 1)
    # Gera order_id no serviço
    order_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)

    # Verifica crédito ativo
    res = (
        supabase
        .table("creditos")
        .select("*")
        .eq("placa", placa)
        .gte("expira_em", now_utc.isoformat())
        .execute()
    )
    ativo = res.data[0] if res.data else None

    if ativo:
        exp_atual = datetime.fromisoformat(ativo["expira_em"])
        nova_exp = exp_atual + timedelta(hours=horas)
        supabase.table("creditos").update({
            "expira_em": nova_exp.isoformat(),
            "pagamento_id": order_id
        }).eq("id", ativo["id"]).execute()
        msg = f"Crédito estendido até {nova_exp.isoformat()}."
    else:
        comprou_em = now_utc.isoformat()
        expira_em = (now_utc + timedelta(hours=horas)).isoformat()
        supabase.table("creditos").insert({
            "placa": placa,
            "pagamento_id": order_id,
            "zona": data.get("zona"),
            "comprado_em": comprou_em,
            "expira_em": expira_em,
            "origem": data.get("origem", "app")
        }).execute()
        msg = f"Crédito novo válido até {expira_em}."

    return {"success": True, "order_id": order_id, "message": msg}

def on_purchase(ch, method, props, body):
    data = json.loads(body)
    print("🪙 Recebido:", data)
    resposta = process_purchase(data)

    if props.reply_to:
        # devolve correção no default exchange para a fila de callback
        ch.basic_publish(
            exchange='',
            routing_key=props.reply_to,
            properties=pika.BasicProperties(
                correlation_id=props.correlation_id,
                content_type='application/json'
            ),
            body=json.dumps(resposta)
        )
        print(f"🪙 Resposta enviada (corr_id={props.correlation_id[:8]}...)")

    ch.basic_ack(delivery_tag=method.delivery_tag)

print("🪙 Servidor de crédito rodando na fila", QUEUE_NAME)
ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_purchase)
ch.start_consuming()