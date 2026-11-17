# Projeto 2 - Estufa inteligente na plataforma FIWARE

CCM520 - Internet das Coisas | Centro Universitário FEI

> Rascunho. Os trechos marcados com `TODO` são do grupo (decisões, análises, valores medidos) e precisam ser escritos por vocês. Compare também com o `Modelo de README do grupo.md` do Moodle e ajuste a estrutura se for diferente.

## 1. Identificação

| Campo | Valor |
|---|---|
| Integrantes | TODO: nomes e RAs |
| API key do grupo | `0257` |
| Dispositivo | `estufa001` |
| Entidade NGSI | `urn:ngsi-ld:Greenhouse:001` (tipo `Greenhouse`) |
| Serviço / caminho | `fei` / `/estufa` |
| Repositório | TODO: link do GitHub |

## 2. Objetivo

TODO: descrever com as palavras do grupo o objetivo do projeto (estufa gerenciada por contexto: ESP32, IoT Agent JSON, Orion, Cygnus, MySQL e Grafana).

## 3. Arquitetura

Caminho das medidas (norte):

```
ESP32 / Wokwi -> broker.hivemq.com -> ponte -> Mosquitto local -> IoT Agent JSON -> Orion -> subscrições (Cygnus e alerta)
```

Caminho dos comandos (sul):

```
Orion -> IoT Agent JSON -> Mosquitto local -> ponte -> broker.hivemq.com -> ESP32 / Wokwi
```

Histórico e visualização: `Orion -> Cygnus -> MySQL -> Grafana`.

Serviços do `docker-compose.yml`: Orion (+ MongoDB), IoT Agent JSON, Mosquitto, consumidor, Cygnus, MySQL e Grafana.

| Serviço | Porta (host) | Uso |
|---|---|---|
| Orion | 1026 | API NGSI-v2 |
| IoT Agent JSON | 4041 | provisionamento (grupos e dispositivos) |
| Mosquitto | 1883 | broker local, lado da ponte |
| Cygnus | 5050 / 5080 | notificações do Orion / API de gestão |
| Grafana | 3000 | painel |
| Consumidor | 3001 | alertas (acessado pelo Orion como `consumidor:3000`) |
| MySQL | 3306 | banco `fei`, tabela `estufa` |

TODO: conferir as portas no seu `docker-compose.yml` e incluir o diagrama da arquitetura, se quiserem.

## 4. Como subir o ambiente

1. Instale Docker Desktop e Postman.
2. Na pasta `plataforma/`:

```bash
docker compose up -d
docker compose ps
```

3. Confira que todos os serviços estão `running` e o MySQL, `healthy`.
4. Para encerrar sem perder dados: `docker compose stop`. Evite `docker compose down -v`, que apaga os volumes.

## 5. Ponte MQTT (Mosquitto <-> HiveMQ)

A ponte só deixa passar os tópicos da API key do grupo:

| Tópico | Direção | Quem publica |
|---|---|---|
| `/json/0257/estufa001/attrs` | in (HiveMQ -> local) | ESP32 |
| `/json/0257/estufa001/cmdexe` | in (HiveMQ -> local) | ESP32 |
| `/0257/estufa001/cmd` | out (local -> HiveMQ) | IoT Agent |

TODO: indicar o `remote_clientid` usado na ponte e explicar por que ele inclui a API key.

## 6. Modelo de dados

### 6.1 Atributos de medida (contrato entre firmware e provisionamento)

| Grandeza | Atributo NGSI | `object_id` | Tipo | Faixa |
|---|---|---|---|---|
| Temperatura do ar | `temperature` | `t` | Number | °C |
| Umidade relativa do ar | `relativeHumidity` | `rH` | Number | % |
| Umidade do solo | `soilMoisture` | `sM` | Number | 0 seco, 100 encharcado |
| Luminosidade | `illuminance` | `ilm` | Number | 0 escuro, 100 claro |
| Estado do relé | `relayState` | `rS` | Number | 0 ou 1 |
| Ângulo da janela | `windowAngle` | `wA` | Number | 0 a 180 |
| Intervalo de coleta | `samplingInterval` | `sI` | Number | 2 a 10 s |

### 6.2 Comandos

| Comando | Valor | Efeito |
|---|---|---|
| `setRelay` | 0 ou 1 | desliga / liga o relé |
| `setServo` | 0 a 180 | posiciona a janela |
| `setInterval` | 2 a 10 | intervalo de coleta (s) |
| `setSending` | 0 ou 1 | desativa / ativa o envio das medidas |

A estufa responde todo comando com `OK` ou `ERRO: <motivo>`. Valor inválido nunca altera o estado. Com `setSending = 0` as medidas param, mas os comandos continuam funcionando.

### 6.3 Atributos estáticos

| Atributo | Tipo | Valor |
|---|---|---|
| `name` | Text | `Estufado` |
| `location` | geo:json | Point, coordenadas `[-46.63, -23.55]` (longitude, latitude) |

## 7. Provisionamento (IoT Agent)

- **Grupo de serviço** (`POST /iot/groups`, lista `groups`): `apikey` `0257`, `entity_type` `Greenhouse`, `resource` `/iot/json`, `cbroker` `http://orion:1026`, `autoprovision` `false`.
- **Dispositivo** (`POST /iot/devices`, lista `devices`): `device_id` `estufa001`, transporte MQTT, 7 atributos, 4 comandos e 2 estáticos conforme a seção 6.
- Cabeçalhos em todas as requisições ao IoT Agent e ao Orion: `fiware-service: fei` e `fiware-servicepath: /estufa`.

TODO: explicar com as palavras do grupo por que `autoprovision` está desligado e o que foi observado ao receber medidas de dispositivos não provisionados (`MEASURES-004`).

## 8. Firmware e circuito (Wokwi)

Arquivo: `firmware/main.py` (MicroPython, ESP32). Wi-Fi do Wokwi: `Wokwi-GUEST`, sem senha. Client id MQTT: `esp32_0257_estufa001`.

| Componente | Pino | Observação |
|---|---|---|
| Umidade do solo | GPIO34 (ADC1) | no Wokwi, simulada por potenciômetro |
| Luminosidade (LDR) | GPIO35 (ADC1) | módulo com saída analógica |
| DHT22 | GPIO4 | temperatura e umidade do ar |
| Relé | GPIO26 | saída digital |
| Servo | GPIO27 | PWM a 50 Hz |

Tópicos usados pelo firmware:

| Sentido | Tópico |
|---|---|
| Medidas (publica) | `/json/0257/estufa001/attrs` |
| Comandos (assina) | `/0257/estufa001/cmd` |
| Resultado (publica) | `/json/0257/estufa001/cmdexe` |

### Calibração

| Constante | Valor | Critério |
|---|---|---|
| `SOIL_DRY_RAW` | 0 | TODO: confirmar o valor medido e o critério |
| `SOIL_WET_RAW` | 4095 | TODO: confirmar o valor medido e o critério |
| `LIGHT_DARK_RAW` | TODO | TODO: medir no módulo LDR |
| `LIGHT_BRIGHT_RAW` | TODO | TODO: medir no módulo LDR |
| Servo (`duty` em 0° e 180°) | TODO | TODO: medir no Wokwi |

TODO: registrar como a calibração foi feita e anexar o diagrama do circuito.

## 9. Subscrições

| Subscrição | Condição | Destino | Atributos | Formato |
|---|---|---|---|---|
| Histórico | entidades `Greenhouse` | `http://cygnus:5050/notify` | os 7 atributos de medida | `normalized` |
| Alerta de solo seco | `soilMoisture<30` | `http://consumidor:3000/alerta-estufa` | `soilMoisture`, `relayState`, `TimeInstant` | `keyValues` |

A subscrição de alerta usa `throttling` de 60 s, para não notificar a cada medida enquanto o solo estiver seco.

TODO: justificar a escolha do `throttling`.

## 10. Painel no Grafana

Dashboard **Estufa inteligente** (atualização automática de 5 s), fonte MySQL com o usuário somente leitura `grafana`, banco `fei`:

| Item | Painel | Atributo(s) |
|---|---|---|
| a | Série temporal | `temperature` e `relativeHumidity` |
| b | Série temporal | `soilMoisture` |
| c | State timeline | `relayState` |
| d | Stat ou Gauge | `illuminance` (valor atual) |

O Cygnus grava todas as colunas como texto, então as consultas usam `CAST` no `SELECT`, e nunca dentro das macros `$__timeFilter`. Exportação: `grafana/painel-estufa.json`.

## 11. Testes e demonstração

Roteiro do ciclo completo:

1. `setRelay = 1` enviado pelo Orion (`PATCH /v2/entities/urn:ngsi-ld:Greenhouse:001/attrs`).
2. A estufa responde e o Orion mostra `setRelay_status` e `setRelay_info`.
3. A nova medida traz `relayState = 1`.
4. O Cygnus grava no MySQL.
5. O Grafana mostra o relé ligado.

Coleção Postman: rodar as pastas no Runner com a estufa ligada. Use um **delay de 3000 a 5000 ms** entre requisições. Sem ele, algumas verificações falham porque consultam o Orion antes de a resposta da ESP32 voltar pelo broker público.

TODO: anexar o resultado exportado do Runner e capturas de tela do painel.

## 12. Segurança e limitações

TODO: discutir, com as palavras do grupo, os riscos de usar um broker público (ausência de autenticação, colisão de client id, assinatura compartilhada) e o que foi feito para mitigá-los (API key única, IoT Agent no Mosquitto local, ponte filtrada).

## 13. Decisões de projeto

TODO: registrar as decisões do grupo (escolha dos `object_id`, valores de `throttling`, formatos de subscrição, simulação do sensor de solo por potenciômetro, etc.) e as dificuldades encontradas.

## 14. Estrutura do repositório

```
projeto2-<Nome>-0257/
├── README.md
├── firmware/main.py
├── plataforma/
│   ├── docker-compose.yml
│   └── mosquitto/ mysql/ servicos/
├── postman/
├── grafana/painel-estufa.json
└── relatorio.pdf
```

Não suba a senha real do Wi-Fi para o repositório.

## 15. Referências

- Material das Aulas 5 a 9 e documentos de apoio do Moodle
- fiware-iotagent-json.readthedocs.io
- fiware-orion.readthedocs.io
- hivemq.com/mqtt
