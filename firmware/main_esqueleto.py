"""
============================================================================
 CCM520 - Internet das Coisas | Projeto 2 - Estufa inteligente na plataforma FIWARE
 Centro Universitario FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 Linguagem: MicroPython (firmware ESP32_GENERIC) - placa real ou Wokwi
----------------------------------------------------------------------------
 ENUNCIADO
   Leve a estufa do Projeto 1 para a plataforma FIWARE. O circuito e o
   mesmo; o que muda e QUEM conversa com a ESP32: em vez de voce mandar
   comandos pelo HiveMQ WebSocket Client, quem publica e assina os topicos
   agora e o IoT Agent JSON, que traduz tudo para o Orion (NGSI-v2).

   O broker continua sendo o PUBLICO: broker.hivemq.com, porta 1883. A
   plataforma enxerga os topicos da sua API key por uma ponte (bridge)
   entre o broker publico e o Mosquitto local, configurada na Etapa 1.

 O QUE MUDA EM RELACAO AO PROJETO 1
   topicos ..... deixam de ser /fei/<id>/<grandeza> e passam a seguir a
                 convencao do IoT Agent JSON (Aula 8): um topico de
                 medidas, um de comandos e um de resultado de comandos
   payload ..... UM JSON com todas as medidas, com as chaves curtas
                 (object_id) que voce definir no provisionamento
   comandos .... chegam como JSON {"<comando>": <valor>} e TODO comando
                 precisa de resposta no topico de resultado
   Ativar / Desativar / Atualizar:N -> viram comandos NGSI (tabela abaixo)

 COMANDOS OBRIGATORIOS (os nomes sao fixos: a plataforma depende deles)
   setRelay     0 ou 1         desliga / liga o rele (irrigacao/ventilacao)
   setServo     0 a 180        angulo da janela/cortina de sombreamento
   setInterval  2 a 10         intervalo de coleta, em segundos
   setSending   0 ou 1         desativa / ativa o envio das medidas
   Resposta: "OK" quando executou, ou "ERRO: <motivo>" quando recusou.
   Valor invalido NUNCA muda o estado da estufa.

 REQUISITOS
   [ ] as medidas (4 sensores + estado do rele + angulo do servo +
       intervalo atual) sao publicadas em UM JSON, a cada "intervalo";
   [ ] numeros vao como numeros (25.3), nunca como texto ("25.3");
   [ ] os 4 comandos funcionam e TODOS recebem resposta no topico de
       resultado, com a chave igual ao nome do comando;
   [ ] com setSending = 0 as medidas param, mas os comandos continuam
       sendo executados e respondidos (inclusive o setSending = 1);
   [ ] mensagem invalida (texto, JSON quebrado, comando desconhecido)
       nunca derruba o programa;
   [ ] o laco principal nao usa time.sleep() nem client.wait_msg().

 LIGACOES DO CIRCUITO (as mesmas do Projeto 1)
   Umidade do solo (capacitivo) . AOUT -> GPIO34 (ADC1_CH6)
   LDR em divisor de tensao ..... ponto medio -> GPIO35 (ADC1_CH7)
   DHT22 ........................ DATA -> GPIO4
   Rele de 1 canal .............. IN -> GPIO26
   Servomotor ................... sinal -> GPIO27 (alimentacao em 5V/Vin)

 ORDEM SUGERIDA (siga o README do Projeto 2)
   TODO 1 e 2 -> rode e confira as medidas no Orion (Etapa 3, passo 3.2)
   TODO 3 e 4 -> rode e envie os comandos pelo Orion (Etapa 3, passo 3.4)
   TODO 5     -> setSending e setInterval (Etapa 3, passo 3.5)
 Teste a cada bloco. Nao escreva o arquivo inteiro antes do primeiro teste.
============================================================================
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
SSID = "nome_da_rede"            # no Wokwi: "Wokwi-GUEST"
SENHA = "senha_da_rede"          # no Wokwi: ""  (NUNCA suba sua senha real para o GitHub)

BROKER = "broker.hivemq.com"
PORTA = 1883

API_KEY = "troqueesteid"         # TODO: a API key do grupo (a mesma da ponte e do provisionamento)
DEVICE_ID = "estufa001"          # o MESMO device_id provisionado no IoT Agent

# No broker publico o client id precisa ser UNICO: dois clientes com o mesmo
# id derrubam um ao outro.
CLIENT_ID = "esp32_" + API_KEY + "_" + DEVICE_ID

# TODO 1: monte os tres topicos do IoT Agent JSON a partir de API_KEY e
#         DEVICE_ID (convencao da Aula 8). Atencao ao prefixo /json: ele
#         aparece em dois deles e nao aparece no outro.
TOPICO_MEDIDAS = "____"          # a ESP32 PUBLICA as medidas aqui
TOPICO_COMANDOS = "____"         # a ESP32 ASSINA este topico
TOPICO_RESULTADO = "____"        # a ESP32 PUBLICA a resposta de cada comando aqui

INTERVALO_MIN = 2000             # ms
INTERVALO_MAX = 10000            # ms
intervalo = 3000                 # ms -- alterado pelo comando setInterval
envio_ativo = True               # alterado pelo comando setSending

# ---------------------------------------------------------------------------
# 2. Hardware (mesmos pinos do Projeto 1)
# ---------------------------------------------------------------------------
sensor_umidade_solo = ADC(Pin(34))
sensor_umidade_solo.atten(ADC.ATTN_11DB)     # faixa de leitura ~0-3.3V

sensor_luz = ADC(Pin(35))
sensor_luz.atten(ADC.ATTN_11DB)

sensor_dht22 = dht.DHT22(Pin(4))

rele = Pin(26, Pin.OUT)
rele.value(0)

servomotor = PWM(Pin(27), freq=50)
angulo_servo = 0                 # ultimo angulo aplicado (0 a 180)


def mover_servo(angulo):
    """Reaproveite a sua conversao angulo -> duty do Projeto 1."""
    global angulo_servo
    angulo_servo = angulo
    servomotor.duty(int(40 + angulo / 180 * 75))   # ajuste para o SEU servomotor


mover_servo(0)


def ler_sensores():
    """Devolve um dicionario com as 4 grandezas, ja convertidas.

    TODO 2a: reaproveite a leitura e a calibracao do Projeto 1.
      - temperatura (C) e umidade do ar (%) vem do DHT22 (measure() antes);
      - umidade do solo em % (0 = seco, 100 = encharcado): calibre os
        valores do ADC para o SEU sensor e documente no README;
      - luminosidade em % (0 = escuro, 100 = claro), tambem calibrada.
    Se o DHT22 falhar (OSError), devolva None: a medida desse ciclo e
    descartada, mas o programa continua.
    """
    return None


# ---------------------------------------------------------------------------
# 3. Wi-Fi -- NAO ALTERE
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
# 4. Medidas (trafego NORTE: ESP32 -> IoT Agent -> Orion)
# ---------------------------------------------------------------------------
def publicar_medidas():
    """TODO 2b: publique UM JSON em TOPICO_MEDIDAS com:
         - as 4 grandezas de ler_sensores();
         - o estado atual do rele (0/1) e o angulo atual do servo;
         - o intervalo atual, em segundos.
       As chaves do JSON sao os object_id que VOCE definiu no
       provisionamento (Etapa 2): se forem diferentes, o IoT Agent
       cria atributos com nomes errados no Orion.
       Use json.dumps() e imprima o payload no Shell para conferir.
    """
    pass


# ---------------------------------------------------------------------------
# 5. Comandos (trafego SUL: Orion -> IoT Agent -> ESP32)
# ---------------------------------------------------------------------------
def executar_comando(nome, valor):
    """Executa UM comando e devolve o texto da resposta.

    TODO 3: setRelay e setServo.
    TODO 5: setInterval e setSending.
      - valor fora da faixa ou de tipo errado -> "ERRO: <motivo>",
        sem mudar o estado;
      - comando desconhecido -> "ERRO: comando desconhecido";
      - executou -> "OK".
    Dica: o valor chega como o Orion recebeu (1, "1", 1.0 ...).
    Converta e trate as excecoes (ValueError, TypeError).
    """
    global intervalo, envio_ativo
    return "ERRO: comando desconhecido"


def ao_receber(topico, mensagem):
    """Callback do MQTT. O IoT Agent envia {"<comando>": <valor>}.

    TODO 4:
      - converta a mensagem com json.loads(); se nao for um JSON valido
        (ou nao for um dicionario), ignore sem travar;
      - para CADA comando recebido, chame executar_comando() e guarde a
        resposta em um dicionario {"<comando>": "<resposta>"};
      - publique esse dicionario em TOPICO_RESULTADO;
      - se o envio estiver ativo, publique as medidas logo em seguida,
        para o novo estado dos atuadores aparecer no Orion na hora.
    """
    print("comando <-", topico, mensagem)


# ---------------------------------------------------------------------------
# 6. Broker
# ---------------------------------------------------------------------------
cliente = MQTTClient(CLIENT_ID, BROKER, port=PORTA, keepalive=60)
cliente.set_callback(ao_receber)
cliente.connect()
# TODO 4 (continuacao): assine o topico de comandos.
print("Conectado a", BROKER, "como", CLIENT_ID)

# ---------------------------------------------------------------------------
# 7. Laco principal -- nada aqui pode bloquear
# ---------------------------------------------------------------------------
ultimo_envio = time.ticks_ms() - intervalo

while True:
    # TODO 2c: verifique comandos sem travar (check_msg) e, se o envio
    #          estiver ativo e ja tiver passado "intervalo" desde o ultimo
    #          envio, publique as medidas e atualize ultimo_envio.
    #          Chame gc.collect() de vez em quando para liberar memoria.
    pass

"""
============================================================================
 CHECKLIST ANTES DE MOSTRAR AO PROFESSOR
----------------------------------------------------------------------------
 [ ] o Shell mostra um JSON de medidas a cada ciclo, com numeros (sem aspas)
 [ ] o HiveMQ WebSocket Client (ou o MQTTX) mostra as medidas no topico de
     medidas e as respostas no topico de resultado
 [ ] a entidade da estufa no Orion e atualizada a cada ciclo (TimeInstant)
 [ ] setRelay e setServo pelo Orion mudam o atuador e o _status vira OK
 [ ] setServo = 200 e setInterval = 30 sao recusados (_info com ERRO) e o
     estado NAO muda
 [ ] setSending = 0 para as medidas; setSending = 1 volta a envia-las
 [ ] setInterval = 5 muda o intervalo (confira no TimeInstant do Orion)
 [ ] uma mensagem qualquer ("teste") no topico de comandos nao derruba o
     programa
 [ ] nao ha nenhum time.sleep() nem wait_msg() dentro do while
 [ ] a senha do Wi-Fi NAO esta no repositorio
============================================================================
"""
