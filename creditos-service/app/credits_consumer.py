import os
import json
import pika
from supabase_client import supabase
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
env = os.environ

# Configuração do RabbitMQ
credentials = pika.PlainCredentials(env["RABBITMQ_USER"], env["RABBITMQ_PASS"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=env["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()

for queue in ["queue_credito", "credit_list", "credit_response"]:
    channel.queue_declare(queue=queue, durable=True)

# Função de processamento de compra de crédito
def process_purchase(data):
    try:
        placa = data["placa"]
        horas = data.get("duracao_horas", 1)
        order_id = data.get("order_id") # <-- Captura o order_id do evento
        now_utc = datetime.now(timezone.utc)

        res = supabase.table("creditos").select("*").eq("placa", placa).gte("expira_em", now_utc.isoformat()).execute()
        active_credit = res.data[0] if res.data else None

        if active_credit:
            print(f"🪙 Crédito ativo encontrado para a placa {placa}. Adicionando tempo.")
            expira_em_atual = datetime.fromisoformat(active_credit["expira_em"])
            nova_expiracao = expira_em_atual + timedelta(hours=horas)
            
            # Atualiza o crédito, mantendo o pagamento_id original
            supabase.table("creditos").update({
                "expira_em": nova_expiracao.isoformat(),
                "pagamento_id": order_id # Atualiza com o ID do novo pagamento que estendeu o tempo
            }).eq("id", active_credit["id"]).execute()
            
        else:
            print(f"🪙 Nenhum crédito ativo para a placa {placa}. Criando novo crédito.")
            comprado_em = now_utc.isoformat()
            expira_em = (now_utc + timedelta(hours=horas)).isoformat()

            record = {
                "placa": placa,
                "pagamento_id": order_id, # <-- Salva o ID do pagamento
                "zona": data.get("zona"),
                "comprado_em": comprado_em,
                "expira_em": expira_em,
                "origem": data.get("origem", "app"),
            }
            supabase.table("creditos").insert(record).execute()

    except Exception as e:
        print(f"🪙 ERRO no processamento de crédito: {str(e)}")

# Função de listagem (não precisa de alteração)
def process_list(data):
    try:
        placa = data["placa"]
        res = supabase.table("creditos").select("*").eq("placa", placa).execute()
        return {"success": True, "credits": res.data}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Callback para compra
def on_purchase(ch, method, props, body):
    msg = json.loads(body)
    print("🪙 Processando compra de crédito:", msg)
    process_purchase(msg) # Apenas processa, não retorna nada
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Callback para listagem
def on_list(ch, method, props, body):
    msg = json.loads(body)
    corr_id = msg.get("correlation_id")
    print("🪙 Listando créditos para placa:", msg.get("placa"))
    response = process_list(msg)
    response["correlation_id"] = corr_id
    channel.basic_publish(
        exchange="",
        routing_key="credit_response",
        properties=pika.BasicProperties(correlation_id=corr_id),
        body=json.dumps(response),
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Inicia o consumo das filas
def start_consuming():
    channel.basic_consume(queue="queue_credito", on_message_callback=on_purchase)
    channel.basic_consume(queue="credit_list", on_message_callback=on_list)
    print("🪙 Credit Service rodando. Aguardando mensagens...")
    channel.start_consuming()
