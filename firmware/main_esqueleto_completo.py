"""
CCM520 - Internet das Coisas | Projeto 2 - Estufa inteligente FIWARE
Firmware MicroPython para ESP32_GENERIC.

Object IDs adotados neste firmware (use exatamente os mesmos no provisionamento):
  t   -> temperature
  rH  -> relativeHumidity
  sM  -> soilMoisture
  ilm -> illuminance
  rS  -> relayState
  wA  -> windowAngle
  sI  -> samplingInterval

IMPORTANTE: ajuste SOIL_DRY_RAW, SOIL_WET_RAW, LIGHT_DARK_RAW e
LIGHT_BRIGHT_RAW usando as leituras reais do seu circuito/sensores.
"""

import dht
import gc
import json
import network
import time
from machine import ADC, Pin, PWM
from umqtt.simple import MQTTClient


# ---------------------------------------------------------------------------
# 1. Configuracao
# ---------------------------------------------------------------------------
SSID = "Wokwi-GUEST"
SENHA = ""

BROKER = "broker.hivemq.com"
PORTA = 1883

API_KEY = "0257"       # Troque pela API key unica do grupo
DEVICE_ID = "estufa001"

CLIENT_ID = "esp32_" + API_KEY + "_" + DEVICE_ID

# Convencao do IoT Agent JSON / ponte MQTT (README, secao 1.3)
TOPICO_MEDIDAS = "/json/" + API_KEY + "/" + DEVICE_ID + "/attrs"
TOPICO_COMANDOS = "/" + API_KEY + "/" + DEVICE_ID + "/cmd"
TOPICO_RESULTADO = "/json/" + API_KEY + "/" + DEVICE_ID + "/cmdexe"

INTERVALO_MIN = 2000
INTERVALO_MAX = 10000
intervalo = 3000
envio_ativo = True


# ---------------------------------------------------------------------------
# 2. Calibracao dos sensores
# ---------------------------------------------------------------------------
# Substitua estes valores pelos valores RAW medidos no seu Projeto 1.
# A funcao de conversao aceita tanto sensores cuja leitura cresce quanto
# sensores cuja leitura diminui com a grandeza fisica.
SOIL_DRY_RAW = 0
SOIL_WET_RAW = 4095
LIGHT_DARK_RAW = 0
LIGHT_BRIGHT_RAW = 4095


# ---------------------------------------------------------------------------
# 3. Hardware
# ---------------------------------------------------------------------------
sensor_umidade_solo = ADC(Pin(34))
sensor_umidade_solo.atten(ADC.ATTN_11DB)

sensor_luz = ADC(Pin(35))
sensor_luz.atten(ADC.ATTN_11DB)

sensor_dht22 = dht.DHT22(Pin(4))

rele = Pin(26, Pin.OUT)
rele.value(0)

servomotor = PWM(Pin(27), freq=50)
angulo_servo = 0


def limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def converter_percentual(leitura, valor_zero, valor_cem):
    """Mapeia uma leitura ADC calibrada para 0..100%, inclusive invertida."""
    if valor_zero == valor_cem:
        return 0.0
    percentual = (leitura - valor_zero) * 100.0 / (valor_cem - valor_zero)
    return round(limitar(percentual, 0.0, 100.0), 1)


def mover_servo(angulo):
    """Converte 0..180 graus para duty; ajuste se seu servo exigir."""
    global angulo_servo
    angulo_servo = angulo
    servomotor.duty(int(40 + angulo / 180 * 75))


mover_servo(0)


def ler_sensores():
    """Retorna as quatro grandezas; em falha do DHT22 descarta o ciclo."""
    try:
        sensor_dht22.measure()
        temperatura = sensor_dht22.temperature()
        umidade_ar = sensor_dht22.humidity()

        solo_raw = sensor_umidade_solo.read()
        luz_raw = sensor_luz.read()

        return {
            "t": round(float(temperatura), 1),
            "rH": round(float(umidade_ar), 1),
            "sM": converter_percentual(
                solo_raw, SOIL_DRY_RAW, SOIL_WET_RAW
            ),
            "ilm": converter_percentual(
                luz_raw, LIGHT_DARK_RAW, LIGHT_BRIGHT_RAW
            )
        }
    except OSError as erro:
        print("Falha na leitura do DHT22; ciclo descartado:", erro)
        return None
    except Exception as erro:
        print("Falha ao ler sensores; ciclo descartado:", erro)
        return None


# ---------------------------------------------------------------------------
# 4. Wi-Fi
# ---------------------------------------------------------------------------
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

if not wlan.isconnected():
    wlan.connect(SSID, SENHA)
    inicio = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), inicio) > 15000:
            raise RuntimeError("Wi-Fi nao conectou")
        time.sleep(0.5)

print("Wi-Fi ok. IP:", wlan.ifconfig()[0])


# ---------------------------------------------------------------------------
# 5. Medidas: ESP32 -> IoT Agent -> Orion
# ---------------------------------------------------------------------------
def publicar_medidas():
    medidas = ler_sensores()
    if medidas is None:
        return False

    # Object IDs curtos devem coincidir com os do provisionamento.
    medidas.update({
        "rS": int(rele.value()),
        "wA": int(angulo_servo),
        "sI": int(intervalo // 1000)
    })

    payload = json.dumps(medidas)
    print("medidas ->", payload)
    cliente.publish(TOPICO_MEDIDAS, payload)
    return True


# ---------------------------------------------------------------------------
# 6. Comandos: Orion -> IoT Agent -> ESP32
# ---------------------------------------------------------------------------
def converter_inteiro(valor, nome):
    # O Orion pode entregar 1, 1.0 ou "1". Aceita essas representacoes,
    # mas recusa bool, texto nao numerico e numeros fracionarios.
    if isinstance(valor, bool):
        raise ValueError(nome + " deve ser um numero inteiro")
    if not isinstance(valor, (int, float, str)):
        raise ValueError(nome + " deve ser um numero inteiro")
    try:
        numero = float(valor)
    except (ValueError, TypeError):
        raise ValueError(nome + " deve ser um numero inteiro")
    if int(numero) != numero:
        raise ValueError(nome + " deve ser um numero inteiro")
    return int(numero)


def executar_comando(nome, valor):
    """Executa o comando validado; valor invalido nunca altera o estado."""
    global intervalo, envio_ativo

    try:
        if nome == "setRelay":
            novo_estado = converter_inteiro(valor, nome)
            if novo_estado not in (0, 1):
                return "ERRO: setRelay aceita apenas 0 ou 1"
            rele.value(novo_estado)

        elif nome == "setServo":
            novo_angulo = converter_inteiro(valor, nome)
            if not 0 <= novo_angulo <= 180:
                return "ERRO: setServo aceita valores de 0 a 180"
            mover_servo(novo_angulo)

        elif nome == "setInterval":
            segundos = converter_inteiro(valor, nome)
            if not 2 <= segundos <= 10:
                return "ERRO: setInterval aceita valores de 2 a 10 segundos"
            intervalo = segundos * 1000

        elif nome == "setSending":
            novo_estado = converter_inteiro(valor, nome)
            if novo_estado not in (0, 1):
                return "ERRO: setSending aceita apenas 0 ou 1"
            envio_ativo = (novo_estado == 1)

        else:
            return "ERRO: comando desconhecido"

        print("comando executado:", nome, valor)
        return "OK"

    except (ValueError, TypeError, OverflowError) as erro:
        return "ERRO: " + str(erro)


def ao_receber(topico, mensagem):
    """Processa comandos JSON e sempre responde a cada comando reconhecido."""
    print("comando <-", topico, mensagem)

    try:
        dados = json.loads(mensagem)
    except (ValueError, TypeError) as erro:
        print("JSON invalido ignorado:", erro)
        return

    if not isinstance(dados, dict):
        print("Mensagem ignorada: o JSON precisa ser um objeto")
        return

    if not dados:
        print("Mensagem ignorada: objeto JSON vazio")
        return

    respostas = {}
    for nome, valor in dados.items():
        respostas[nome] = executar_comando(nome, valor)

    try:
        payload_resposta = json.dumps(respostas)
        print("resultado ->", payload_resposta)
        cliente.publish(TOPICO_RESULTADO, payload_resposta)
    except OSError as erro:
        print("Falha ao publicar resposta MQTT:", erro)
        return

    # Atualiza o Orion imediatamente após os comandos/atuadores, se habilitado.
    if envio_ativo:
        try:
            publicar_medidas()
        except OSError as erro:
            print("Falha ao publicar medidas apos comando:", erro)


# ---------------------------------------------------------------------------
# 7. Broker
# ---------------------------------------------------------------------------
cliente = MQTTClient(CLIENT_ID, BROKER, port=PORTA, keepalive=60)
cliente.set_callback(ao_receber)
cliente.connect()
cliente.subscribe(TOPICO_COMANDOS)
print("Conectado a", BROKER, "como", CLIENT_ID)
print("Assinando:", TOPICO_COMANDOS)
print("Publicando medidas em:", TOPICO_MEDIDAS)
print("Publicando respostas em:", TOPICO_RESULTADO)


# ---------------------------------------------------------------------------
# 8. Laco principal nao bloqueante
# ---------------------------------------------------------------------------
ultimo_envio = time.ticks_ms() - intervalo
ultimo_gc = time.ticks_ms()
ultimo_ping = time.ticks_ms()

while True:
    # check_msg() retorna imediatamente quando nao ha mensagem.
    try:
        cliente.check_msg()
    except OSError as erro:
        print("Erro MQTT ao verificar comandos:", erro)
    except Exception as erro:
        # Mensagem invalida nunca derruba o programa.
        print("Erro inesperado ao tratar comando:", erro)

    agora = time.ticks_ms()

    if envio_ativo and time.ticks_diff(agora, ultimo_envio) >= intervalo:
        try:
            publicar_medidas()
        except OSError as erro:
            print("Erro MQTT ao publicar medidas:", erro)
        except Exception as erro:
            print("Erro inesperado ao publicar medidas:", erro)
        ultimo_envio = agora

    # Mantem a conexao viva mesmo com setSending = 0 (keepalive = 60 s).
    if time.ticks_diff(agora, ultimo_ping) >= 30000:
        try:
            cliente.ping()
        except OSError as erro:
            print("Erro MQTT no ping:", erro)
        ultimo_ping = agora

    if time.ticks_diff(agora, ultimo_gc) >= 30000:
        gc.collect()
        ultimo_gc = agora