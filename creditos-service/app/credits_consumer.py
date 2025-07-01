import os
import json
import pika
from supabase_client import supabase
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()
env = os.environ

# Configuração do RabbitMQ
credentials = pika.PlainCredentials(env["RABBITMQ_USER"], env["RABBITMQ_PASS"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=env["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()

# Declaração das filas
for queue in ["queue_credito", "credit_list", "credit_response"]:
    channel.queue_declare(queue=queue, durable=True)


# Envia resposta para a fila de retorno
def send_response(corr_id, payload):
    channel.basic_publish(
        exchange="",
        routing_key="credit_response",
        properties=pika.BasicProperties(correlation_id=corr_id),
        body=json.dumps(payload),
    )


# Insere um novo crédito na tabela 'creditos'
def process_purchase(data):
    try:
        placa = data["placa"]
        zona = data.get("zona")
        origem = data.get("origem", "app")
        horas = data.get("duracao_horas", 1)

        comprado_em = datetime.utcnow().isoformat()
        expira_em = (datetime.utcnow() + timedelta(hours=horas)).isoformat()

        record = {
            "placa": placa,
            "zona": zona,
            "comprado_em": comprado_em,
            "expira_em": expira_em,
            "origem": origem,
        }
        res = supabase.table("creditos").insert(record).execute()
        if res.error:
            return {"success": False, "error": res.error.message}

        entry = res.data[0]
        return {
            "success": True,
            "message": "Crédito comprado com sucesso.",
            "credit_id": entry["id"],
        }
    except Exception as e:
        print(f"🪙 ERROR: {str(e)}")
        return {"success": False, "error": str(e)}


# Recupera todos os créditos de uma determinada placa
def process_list(data):
    try:
        placa = data["placa"]
        res = supabase.table("creditos").select("*").eq("placa", placa).execute()
        if res.error:
            return {"success": False, "error": res.error.message}
        return {"success": True, "credits": res.data}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Callback ao receber pedido de compra
def on_purchase(ch, method, props, body):
    msg = json.loads(body)
    corr_id = msg.get("correlation_id")
    print("🪙 Processando compra de crédito:", msg)

    response = process_purchase(msg)
    response["correlation_id"] = corr_id
    send_response(corr_id, response)
    ch.basic_ack(delivery_tag=method.delivery_tag)


# Callback ao receber pedido de listagem
def on_list(ch, method, props, body):
    msg = json.loads(body)
    corr_id = msg.get("correlation_id")
    print("🪙 Listando créditos para placa:", msg.get("placa"))

    response = process_list(msg)
    response["correlation_id"] = corr_id
    send_response(corr_id, response)
    ch.basic_ack(delivery_tag=method.delivery_tag)


# Inicia o consumo das filas
def start_consuming():
    channel.basic_consume(queue="queue_credito", on_message_callback=on_purchase)
    channel.basic_consume(queue="credit_list", on_message_callback=on_list)
    print("🪙 Credit Service rodando. Aguardando mensagens...")
    channel.start_consuming()
