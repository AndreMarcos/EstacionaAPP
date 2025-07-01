# Arquivo: client_mqtt.py

import paho.mqtt.client as mqtt
import json
import uuid
import cmd
import threading
import time

# --- Configurações ---
MQTT_BROKER_HOST = 'localhost'
MQTT_BROKER_PORT = 1883 # Porta padrão do MQTT
USER_ID_FIXO = "a1b2c3d4-e5f6-7890-1234-567890abcdef"
RABBIT_USER = "estaciona_user"
RABBIT_PASS = "estaciona_user"

class MqttRpcClient:
    """
    Classe que encapsula a lógica de RPC (Requisição-Resposta) sobre o protocolo MQTT.
    """
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(RABBIT_USER, RABBIT_PASS)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Dicionários para rastrear as respostas pendentes
        self.response_payloads = {}
        self.response_events = {}

        # Tópico de resposta único para este cliente
        self.response_topic = f"response/client/{uuid.uuid4()}"

        self.client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        self.client.loop_start()  # Inicia a thread de rede em background

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("[INFO] Conectado ao Broker MQTT com sucesso!")
            # Inscreve-se no tópico de resposta assim que a conexão é estabelecida
            client.subscribe(self.response_topic)
            print(f"[INFO] Escutando por respostas no tópico: {self.response_topic}")
        else:
            print(f"[ERRO] Falha ao conectar, código de retorno: {rc}\n")

    def on_message(self, client, userdata, msg):
        # Callback chamado para TODAS as mensagens recebidas
        try:
            payload = json.loads(msg.payload)
            corr_id = payload.get('correlation_id')

            # Se a mensagem tem um correlation_id que estamos esperando...
            if corr_id in self.response_events:
                self.response_payloads[corr_id] = payload
                # ...sinaliza o evento para "acordar" a thread que fez a chamada
                self.response_events[corr_id].set()
        except Exception as e:
            print(f"[ERRO] Falha ao processar a mensagem: {str(e)}")

    def call(self, target_topic, payload):
        corr_id = str(uuid.uuid4())
        
        # Prepara o evento de sincronização para esta chamada específica
        event = threading.Event()
        self.response_events[corr_id] = event

        # Adiciona os metadados de RPC ao payload
        payload['correlation_id'] = corr_id
        payload['reply_to'] = self.response_topic

        # Publica a mensagem de requisição
        self.client.publish(target_topic, json.dumps(payload))
        print(f" [->] Requisição (corr_id={corr_id[:8]}...) enviada para o tópico '{target_topic}'...")

        # Espera pelo evento ser sinalizado (com timeout)
        event_was_set = event.wait(timeout=10)

        # Limpeza
        del self.response_events[corr_id]

        if not event_was_set:
            return {"error": "Timeout: Nenhuma resposta recebida do serviço."}
        
        return self.response_payloads.pop(corr_id)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()


class EstacionamentoShell(cmd.Cmd):
    """Shell interativo para testar o sistema de estacionamento via MQTT."""
    intro = 'Bem-vindo ao cliente MQTT do EstacionaApp. Digite help ou ? para listar os comandos.\n'
    prompt = '(Estacionamento)> '

    def __init__(self):
        super().__init__()
        self.mqtt_client = MqttRpcClient()
        # Damos um pequeno tempo para a conexão ser estabelecida
        time.sleep(1)

    def _publish_simple_message(self, topic_name, payload):
        """Função auxiliar para enviar mensagens "fire-and-forget"."""
        self.mqtt_client.client.publish(topic_name, json.dumps(payload))
        print(f" [✔] Mensagem enviada com sucesso para o tópico '{topic_name}'.")

    def do_cadastrar_veiculo(self, arg):
        """Cadastra um novo veículo para o usuário fixo.
        Uso: cadastrar_veiculo <placa> <modelo> <cor>
        Exemplo: cadastrar_veiculo BRA-2E19 Fusca Azul"""
        try:
            placa, modelo, cor = arg.split()
            payload = {
                "user_id": USER_ID_FIXO,
                "placa": placa.upper(),
                "modelo": modelo,
                "cor": cor
            }
            # No MQTT, o nome do tópico pode ser o mesmo da fila AMQP
            self._publish_simple_message('vehicle_register', payload)
        except ValueError:
            print("Erro: Uso incorreto. Exemplo: cadastrar_veiculo BRA-2E19 Fusca Azul")

    def do_adicionar_credito(self, arg):
        """Inicia o processo de adicionar crédito para um veículo.
        Uso: adicionar_credito <placa> <valor>
        Exemplo: adicionar_credito BRA-2E19 5.50"""
        try:
            placa, zona, valor = arg.split()
            payload = {
                "user_id": USER_ID_FIXO,
                "placa": placa.upper(),
                "zona" : zona,
                "duracao_horas": int(valor)
            }
            response = self.mqtt_client.call('queue_pagamento', payload)
            print("\n--- Resultado da Consulta ---")
            if response.get("error"):
                print(f"ERRO: {response['error']}")
            else:
                status = response.get('status', 'desconhecido').upper()
                mensagem = response.get('message', 'Sem mensagem adicional.')
                print(f"Status: {status}")
                print(f"Mensagem: {mensagem}")
                print("---------------------------\n")
        except (ValueError, IndexError):
            print("Erro: Uso incorreto. Exemplo: adicionar_credito BRA-2E19 A 5")

    def do_consultar_placa(self, arg):
        """Consulta a situação de uma placa. (Função do Fiscal)
        Uso: consultar_placa <placa>
        Exemplo: consultar_placa BRA-2E19"""
        placa = arg.strip().upper()
        if not placa:
            print("Erro: Por favor, informe uma placa.")
            return

        payload = {"placa": placa}
        response = self.mqtt_client.call('queue_fiscalizacao', payload)

        print("\n--- Resultado da Consulta ---")
        if response.get("error"):
            print(f"ERRO: {response['error']}")
        else:
            status = 'REGULAR' if response.get('status', False) else 'IRREGULAR'            
            mensagem = response.get('mensagem', 'Sem mensagem adicional.')
            print(f"Placa: {placa}")
            print(f"Status: {status}")
            print(f"Mensagem: {mensagem}")
            print("---------------------------\n")

            if status == 'IRREGULAR':
                chamar_guarda = input("Veículo irregular. Deseja notificar a guarda? (S/N): ").lower()
                if chamar_guarda.upper == 'S':
                    notification_payload = {
                        "placa": placa,
                        "localizacao": "Rua Principal, 123"
                    }
                    # Envia a confirmação para o serviço de notificação
                    self._publish_simple_message('queue_notificacao', notification_payload)

    def do_exit(self, arg):
        """Sai do programa."""
        print('Encerrando conexão e saindo...')
        self.mqtt_client.disconnect()
        return True
    
    def do_quit(self, arg):
        """Sai do programa."""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """Sai do programa com Ctrl+D."""
        return self.do_exit(arg)


if __name__ == '__main__':
    try:
        EstacionamentoShell().cmdloop()
    except KeyboardInterrupt:
        print("\nSaindo...")