from dotenv import load_dotenv
load_dotenv()  # carrega SUPABASE_URL/SUPABASE_KEY e RabbitMQ antes de qualquer import

import os
import json
import pika

# --- Configurações RabbitMQ ---
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")

# Nome da fila em que o CLI publica a confirmação de multa
QUEUE_NAME = 'fiscalizacao_multa'

# Conexão e canal
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
conn = pika.BlockingConnection(
    pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
)
channel = conn.channel()

# Declara a fila — durável para não perder mensagens em reinício
channel.queue_declare(queue=QUEUE_NAME, durable=True)


def on_notification(ch, method, props, body):
    """
    Callback que processa a confirmação de multa enviada pelo agente.
    Exemplo de payload:
      {
        "placa": "BRA-2E19",
        "localizacao": "Rua Principal, 123"
      }
    """
    try:
        data = json.loads(body)
        placa = data.get('placa', 'N/A')
        local = data.get('localizacao', 'N/A')

        print("\n------ 🚨 MULTA CONFIRMADA 🚨 ------")
        print(f"  Placa:      {placa}")
        print(f"  Localização:{local}")
        print("  Ação:       Acionando Guarda Municipal para emitir multa...")
        print("------------------------------------\n")

        # Aqui você poderia chamar outra API / gravar em banco / etc.
    except Exception as e:
        print(f"[ERROR] falha ao processar notificação de multa: {e}")
    finally:
        # Sempre confirme para remover da fila
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consuming():
    print(f"🚨 Serviço de Notificação rodando — consumindo '{QUEUE_NAME}'...")
    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=on_notification
    )
    channel.start_consuming()


if __name__ == '__main__':
    try:
        start_consuming()
    except KeyboardInterrupt:
        print("\n🔌 Interrompido pelo usuário, fechando conexão...")
        channel.close()
        conn.close()