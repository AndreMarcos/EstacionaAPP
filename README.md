# Administração de Estacionamento Rotativo - Backend

Este repositório contém o código-fonte para o backend do sistema de Administração de Estacionamento Rotativo. A solução é baseada em uma arquitetura de microsserviços orientada a eventos para garantir escalabilidade, resiliência e manutenibilidade.

## Arquitetura e Tecnologias

O ecossistema é containerizado com Docker e orquestrado com Docker Compose. As principais tecnologias utilizadas são:

* **Linguagem:** Python 3.11
* **Mensageria:** RabbitMQ (com plugins de Management e MQTT ativados)
* **Banco de Dados:** Supabase (PostgreSQL)
* **Containerização:** Docker & Docker Compose
* **Principais Bibliotecas:** Pika (para comunicação AMQP entre serviços), Paho-MQTT (para o cliente de teste).

## Pré-requisitos

Antes de iniciar, garanta que você tenha os seguintes softwares instalados:
* [Docker](https://www.docker.com/get-started/)
* [Docker Compose](https://docs.docker.com/compose/install/)

Você também precisará de um projeto ativo no [Supabase](https://supabase.com) para obter as credenciais do banco de dados.

## Como Iniciar o Ambiente

Siga os passos abaixo para construir as imagens e iniciar todos os serviços do backend.

**1. Crie o Arquivo de Variáveis de Ambiente**
Na raiz do projeto, crie um arquivo chamado `.env`. Este arquivo conterá os segredos para conexão com o banco de dados e as credenciais padrão do RabbitMQ. Este arquivo não deve ser enviado para o Git.

Copie o conteúdo abaixo para o seu .env e substitua pelos seus valores do Supabase:

```bash
# Arquivo: .env

# Credenciais do Supabase
SUPABASE_URL="SUA_URL_DO_PROJETO_SUPABASE"
SUPABASE_KEY="SUA_CHAVE_ANON_DO_PROJETO_SUPABASE"

# Credenciais padrão do RabbitMQ
RABBITMQ_DEFAULT_USER="SEU_RABBITMQ_DEFAULT_USER"
RABBITMQ_DEFAULT_PASS="SUA_RABBITMQ_DEFAULT_PASS"

RABBITMQ_USER="SEU_RABBITMQ_USER"
RABBITMQ_PASS="SUA_RABBITMQ_PASS"
```

**3. Construa as Imagens Docker**
Este comando irá ler o Dockerfile de cada microsserviço e construir as imagens necessárias.

```bash
docker-compose build
```

**4. Inicie Todos os Serviços**
Este comando iniciará todos os contêineres em segundo plano (-d). Graças à configuração de healthcheck no RabbitMQ, os microsserviços só iniciarão quando o broker estiver totalmente pronto para aceitar conexões.

```bash
docker-compose up
```
