import requests
from requests.auth import HTTPBasicAuth
import time

# Configurações do RabbitMQ
RABBITMQ_API = "http://localhost:15672/api"
USER = "myuser"
PASSWORD = "mypassword"

auth = HTTPBasicAuth(USER, PASSWORD)

def wait_rabbitmq():
    print("Aguardando RabbitMQ estar disponível...")
    while True:
        try:
            r = requests.get(f"{RABBITMQ_API}/healthchecks/node", auth=auth)
            if r.status_code == 200 and r.json().get("status") == "ok":
                print("RabbitMQ disponível!")
                break
        except requests.exceptions.ConnectionError:
            pass
        print("RabbitMQ não disponível ainda, aguardando 3 segundos...")
        time.sleep(3)

def create_exchange(name, exchange_type="direct", durable=True):
    url = f"{RABBITMQ_API}/exchanges/%2f/{name}"
    data = {
        "type": exchange_type,
        "durable": durable
    }
    resp = requests.put(url, json=data, auth=auth)
    resp.raise_for_status()
    print(f"Exchange '{name}' criada.")

def create_queue(name, durable=True):
    url = f"{RABBITMQ_API}/queues/%2f/{name}"
    data = {
        "durable": durable
    }
    resp = requests.put(url, json=data, auth=auth)
    resp.raise_for_status()
    print(f"Fila '{name}' criada.")

def create_binding(exchange, queue, routing_key):
    url = f"{RABBITMQ_API}/bindings/%2f/e/{exchange}/q/{queue}"
    data = {
        "routing_key": routing_key
    }
    resp = requests.post(url, json=data, auth=auth)
    resp.raise_for_status()
    print(f"Binding criado: exchange='{exchange}' -> queue='{queue}' (routing_key='{routing_key}')")

def main():
    wait_rabbitmq()

    # Criar exchanges
    create_exchange("exchange_placa")
    create_exchange("exchange_pagamento")
    create_exchange("exchange_fiscalizacao")
    create_exchange("exchange_notificacao")
    create_exchange("exchange_auth")

    # Criar filas
    create_queue("queue_placa")
    create_queue("queue_pagamento")
    create_queue("queue_credito")
    create_queue("queue_fiscalizacao")
    create_queue("queue_notificacao")
    create_queue("queue_auth")

    # Criar bindings
    create_binding("exchange_placa", "queue_placa", "placa_key")
    create_binding("exchange_pagamento", "queue_pagamento", "pagamento_key")
    create_binding("exchange_pagamento", "queue_credito", "credito_key")
    create_binding("exchange_fiscalizacao", "queue_fiscalizacao", "fiscalizacao_key")
    create_binding("exchange_notificacao", "queue_notificacao", "notificacao_key")
    create_binding("exchange_auth", "queue_auth", "auth_key")

    print("Setup do RabbitMQ completo!")

if __name__ == "__main__":
    main()