import os
import json
import pika
from supabase_client import supabase
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
env = os.environ

TOPIC_EXCHANGE = 'amq.topic'
ROUTING_KEY_CREDITOS = 'credito.confirmacao.#'
QUEUE_NAME = 'queue_credito'

# Configuração do RabbitMQ
credentials = pika.PlainCredentials(env["RABBITMQ_USER"], env["RABBITMQ_PASS"])
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host=env["RABBITMQ_HOST"], credentials=credentials)
)
channel = connection.channel()


channel.queue_declare(queue=QUEUE_NAME, durable=True)
channel.queue_bind(
    exchange=TOPIC_EXCHANGE,
    queue=QUEUE_NAME,
    routing_key=ROUTING_KEY_CREDITOS
)

# Função de processamento de compra de crédito
def process_purchase(data):
    try:
        placa = data["placa"]
        horas = data.get("duracao_horas", 1)
        order_id = data.get("order_id")
        now_utc = datetime.now(timezone.utc)

        res = supabase.table("creditos").select("*").eq("placa", placa).gte("expira_em", now_utc.isoformat()).execute()
        active_credit = res.data[0] if res.data else None

        message = ""
        if active_credit:
            print(f"🪙 Crédito ativo encontrado para a placa {placa}. Adicionando tempo.")
            expira_em_atual = datetime.fromisoformat(active_credit["expira_em"])
            nova_expiracao = expira_em_atual + timedelta(hours=horas)
            
            supabase.table("creditos").update({
                "expira_em": nova_expiracao.isoformat(),
                "pagamento_id": order_id
            }).eq("id", active_credit["id"]).execute()
            message = f"Tempo de crédito estendido com sucesso até {nova_expiracao.isoformat()}."
        else:
            print(f"🪙 Nenhum crédito ativo para a placa {placa}. Criando novo crédito.")
            comprado_em = now_utc.isoformat()
            expira_em = (now_utc + timedelta(hours=horas)).isoformat()

            record = {
                "placa": placa,
                "pagamento_id": order_id,
                "zona": data.get("zona"),
                "comprado_em": comprado_em,
                "expira_em": expira_em,
                "origem": data.get("origem", "app"),
            }
            supabase.table("creditos").insert(record).execute()
            message = f"Credito comprado com sucesso, valido ate {expira_em}."
        
        # Retorna um dicionário de sucesso
        return {"success": True, "message": message, "order_id": order_id}

    except Exception as e:
        print(f"🪙 ERRO no processamento de crédito: {str(e)}")
        # Retorna um dicionário de erro
        return {"success": False, "error": str(e)}

# Callback para compra
def on_purchase(ch, method, props, body):
    msg = json.loads(body)
    print("🪙 Processando evento de crédito:", msg)
    
    response_payload = process_purchase(msg)
    reply_to = msg.get("reply_to")
    corr_id = props.correlation_id or req.get("correlation_id")

    if reply_to:
        response_payload["correlation_id"] = corr_id
        print(f"🪙 Enviando resposta final para a fila '{reply_to}'")
        channel.basic_publish(
            exchange=TOPIC_EXCHANGE,
            routing_key=reply_to,
            properties=pika.BasicProperties(correlation_id=corr_id),
            body=json.dumps(response_payload)
        )

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_consuming():
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_purchase)
    print("🪙 Credit Service rodando. Aguardando mensagens...")
    channel.start_consuming()
