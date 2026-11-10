"""
============================================================================
 CCM520 - Internet das Coisas | Projeto 2 - EXEMPLO RESOLVIDO
 Centro Universitario FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 LAMPADA INTELIGENTE SIMULADA (Python 3 + paho-mqtt 2.x)

 Um dispositivo completo, menor que a estufa, para voce ver o sistema
 funcionando de ponta a ponta antes de montar o seu. Ela usa os MESMOS
 conceitos que a estufa vai usar: topicos do IoT Agent JSON, um JSON de
 medidas com chaves curtas (object_id), comandos e resposta no cmdexe.

 Sobe junto com a plataforma (docker compose up -d). Para acompanhar:
   docker compose logs -f lampada-simulada

 DIFERENCAS EM RELACAO A ESTUFA
   - fala com o Mosquitto LOCAL (mosquitto:1883), sem passar pela ponte
     nem pelo broker publico: funciona sem internet e nao colide com a
     lampada dos colegas;
   - API key fixa (lampada2026) e caminho de servico proprio (/lampada);
   - 2 medidas e 1 comando (a estufa tem 7 medidas e 4 comandos).

 TOPICOS (IoT Agent JSON, Aula 8)
   medidas   /json/<API_KEY>/<DEVICE_ID>/attrs    (a lampada publica)
   comandos  /<API_KEY>/<DEVICE_ID>/cmd           (a lampada assina)
   resultado /json/<API_KEY>/<DEVICE_ID>/cmdexe   (a lampada publica)

 PAYLOAD DE MEDIDAS (chaves curtas = object_id do provisionamento)
   {"s": estado da lampada (0 apagada | 1 acesa),
    "l": luminosidade do ambiente (%, 0 escuro .. 100 claro)}

 COMANDO
   {"setLight": 0|1}  -> apaga / acende. Resposta: "OK" ou "ERRO: <motivo>".
============================================================================
"""

import json
import math
import os
import random
import time

import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "localhost")      # "mosquitto" dentro do Docker
PORTA = 1883
API_KEY = os.getenv("API_KEY", "lampada2026")
DEVICE_ID = os.getenv("DEVICE_ID", "lampada001")
INTERVALO = int(os.getenv("INTERVALO", "5"))         # segundos entre medidas

TOPICO_MEDIDAS = f"/json/{API_KEY}/{DEVICE_ID}/attrs"
TOPICO_COMANDOS = f"/{API_KEY}/{DEVICE_ID}/cmd"
TOPICO_RESULTADO = f"/json/{API_KEY}/{DEVICE_ID}/cmdexe"

estado = 0                                            # 0 apagada, 1 acesa


def luminosidade():
    """Luz do ambiente: um "dia acelerado" (1 minuto real = 1 hora) + a propria lampada."""
    hora = (time.time() / 60) % 24
    sol = max(0.0, math.sin(math.pi * (hora - 6) / 12))  # 0 a noite, 1 ao meio-dia
    valor = 5 + 60 * sol + (30 if estado else 0) + random.uniform(-3, 3)
    return round(min(100.0, max(0.0, valor)), 1)


def publicar_medidas(cliente):
    medidas = {"s": estado, "l": luminosidade()}        # numeros, nunca texto
    cliente.publish(TOPICO_MEDIDAS, json.dumps(medidas))
    print("medidas   ->", TOPICO_MEDIDAS, medidas, flush=True)
    with open("/tmp/vivo", "w") as arquivo:              # usado pelo healthcheck do Docker
        arquivo.write(str(time.time()))


def executar(nome, valor):
    """Executa UM comando e devolve a resposta. Valor invalido nao muda o estado."""
    global estado
    if nome != "setLight":
        return "ERRO: comando desconhecido"
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return "ERRO: valor deve ser 0 ou 1"
    if valor not in (0, 1):
        return "ERRO: valor deve ser 0 ou 1"
    estado = valor
    return "OK"


def ao_conectar(cliente, userdata, flags, codigo, propriedades=None):
    print("conectado ao broker", BROKER, "- assinando", TOPICO_COMANDOS, flush=True)
    cliente.subscribe(TOPICO_COMANDOS)                  # (re)assina a cada conexao


def ao_receber(cliente, userdata, msg):
    print("comando   <-", msg.topic, msg.payload, flush=True)
    try:
        comandos = json.loads(msg.payload)
    except ValueError:
        return                                          # nao e JSON: ignora sem travar
    if not isinstance(comandos, dict):
        return
    # A chave de cada resposta e o NOME do comando: e assim que o IoT Agent
    # sabe a que comando ela pertence (senao o Orion fica em PENDING).
    resultado = {nome: executar(nome, valor) for nome, valor in comandos.items()}
    cliente.publish(TOPICO_RESULTADO, json.dumps(resultado))
    print("resultado ->", TOPICO_RESULTADO, resultado, flush=True)
    publicar_medidas(cliente)                           # o novo estado aparece no Orion na hora


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim_{API_KEY}_{DEVICE_ID}")
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

while True:                                             # espera o broker subir
    try:
        cliente.connect(BROKER, PORTA, keepalive=60)
        break
    except OSError as erro:
        print("broker indisponivel, tentando de novo:", erro, flush=True)
        time.sleep(3)

cliente.loop_start()                                    # rede em segundo plano
while True:
    publicar_medidas(cliente)
    time.sleep(INTERVALO)
