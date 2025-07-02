
import pika
import uuid
import json
import cmd
import threading
import time

# --- Configurações ---
RABBIT_HOST = '198.27.114.55'
RABBIT_PORT = 5672
RABBIT_USER = 'guest'
RABBIT_PASS = 'guest'
USER_ID_FIXO = "a1b2c3d4-e5f6-7890-1234-567890abcdef"

class RabbitRpcClient:
    """
    Cliente RPC sobre RabbitMQ usando pika.BlockingConnection.
    """
    def __init__(self):
        credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
        params = pika.ConnectionParameters(host=RABBIT_HOST,
                                           port=RABBIT_PORT,
                                           credentials=credentials)
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()

        # Declara fila exclusiva para resposta e obtém seu nome
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        # Armazena estados de resposta
        self.response = None
        self.corr_id = None
        self.lock = threading.Lock()
        self.event = threading.Event()

        # Começa a consumir da fila de respostas
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True
        )

        # Thread para loop de consumo
        self.consume_thread = threading.Thread(target=self._start_consuming, daemon=True)
        self.consume_thread.start()

    def _start_consuming(self):
        self.channel.start_consuming()

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            with self.lock:
                self.response = json.loads(body)
                self.event.set()

    def call(self, queue_name, payload, timeout=10):
        """
        Envia payload (dict) para queue_name e bloqueia até receber a resposta.
        """
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.event.clear()

        # inclui metadados
        payload['correlation_id'] = self.corr_id
        payload['reply_to'] = self.callback_queue

        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
                content_type='application/json'
            ),
            body=json.dumps(payload)
        )
        print(f" [->] Requisição (corr_id={self.corr_id[:8]}...) enviada para '{queue_name}'")

        # aguarda resposta
        if not self.event.wait(timeout):
            return {"error": "Timeout: nenhuma resposta recebida."}

        with self.lock:
            return self.response

    def close(self):
        self.channel.stop_consuming()
        self.connection.close()


class EstacionamentoShell(cmd.Cmd):
    """Shell interativo para testar o sistema de estacionamento via RabbitMQ."""
    intro = 'Bem-vindo ao cliente RabbitMQ do EstacionaApp. help ou ? para comandos.\n'
    prompt = '(Estacionamento)> '

    def __init__(self):
        super().__init__()
        self.rpc = RabbitRpcClient()
        # aguarda a thread de consumo iniciar
        time.sleep(0.5)

    def _publish_simple(self, queue, payload):
        """Envio fire-and-forget."""
        self.rpc.channel.basic_publish(
            exchange='',
            routing_key=queue,
            body=json.dumps(payload),
            properties=pika.BasicProperties(content_type='application/json')
        )
        print(f" [✔] Mensagem enviada para '{queue}'.")

    def do_adicionar_credito(self, arg):
        """
        adicionar_credito <placa> <zona> <duracao_horas>
        Ex: adicionar_credito BRA-2E19 A 5
        """
        try:
            placa, zona, valor = arg.split()
            payload = {
                "user_id": USER_ID_FIXO,
                "placa": placa.upper(),
                "zona": zona,
                "duracao_horas": int(valor)
            }
            resp = self.rpc.call('credito_compra', payload)
            print("\n--- Resultado da Consulta ---")
            if 'error' in resp:
                print(f"ERRO: {resp['error']}")
            else:
                print(f"Sucesso: {str(resp.get('success')).upper()}")
                print(f"ID do Pedido: {str(resp.get('order_id')).upper()}")
                print(f"Mensagem: {resp.get('message')}")
            print("---------------------------\n")
        except ValueError:
            print("Erro: Uso incorreto. Exemplo: adicionar_credito BRA-2E19 A 5")

    def do_consultar_placa(self, arg):
        """
        consultar_placa <placa>
        Ex: consultar_placa BRA-2E19
        """
        placa = arg.strip().upper()
        if not placa:
            print("Erro: informe uma placa.")
            return

        resp = self.rpc.call('fiscalizacao_consulta', {"placa": placa})
        print("\n--- Resultado da Consulta ---")
        if 'error' in resp:
            print(f"ERRO: {resp['error']}")
        else:
            status = 'REGULAR' if resp.get('status') else 'IRREGULAR'
            print(f"Placa: {placa}")
            print(f"Status: {status}")
            print(f"Mensagem: {resp.get('mensagem')}")
            if status == 'IRREGULAR':
                escolha = input("Notificar guarda? (S/N): ").strip().upper()
                if escolha == 'S':
                    self._publish_simple('fiscalizacao_multa', {
                        "placa": placa,
                        "localizacao": "Rua Principal, 123"
                    })
        print("---------------------------\n")

    def do_exit(self, arg):
        """Encerra o cliente e sai."""
        print("Encerrando conexão...")
        self.rpc.close()
        return True

    do_quit = do_exit
    do_EOF = do_exit


if __name__ == '__main__':
    try:
        EstacionamentoShell().cmdloop()
    except KeyboardInterrupt:
        print("\nSaindo...")