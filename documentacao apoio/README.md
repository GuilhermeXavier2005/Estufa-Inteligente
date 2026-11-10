# Projeto 2 — Estufa inteligente na plataforma FIWARE

**CCM520 – Internet das Coisas** · Centro Universitário FEI · **Guia passo a passo**

No Projeto 1 a estufa falava MQTT com o broker público da HiveMQ, e **você** mandava os comandos pelo HiveMQ WebSocket Client. No Projeto 2 o circuito é o mesmo, e a estufa continua no **mesmo broker público**, mas passa a fazer parte de uma **plataforma de contexto**: uma **ponte MQTT** leva os tópicos da sua estufa até o **IoT Agent JSON**, que traduz tudo para o **Orion**. A partir daí, qualquer aplicação lê o estado da estufa, manda comandos, recebe alertas e consulta o histórico **sem falar MQTT**.

Este guia leva você do ambiente vazio até a demonstração final, em **4 etapas**. Cada etapa termina com um **ponto de verificação**: só avance quando ele estiver verde.

> O guia diz **o que** fazer e **como conferir**. O **como fazer** das partes centrais é trabalho do grupo, com base nas Aulas 5 a 9. Os conceitos estão no [Material de apoio](Material%20de%20apoio.md).

---

## 0. Visão geral

### 0.1 O que você define e o que já vem pronto

| Você define | Onde |
| --- | --- |
| 1. A **API key** do grupo | `plataforma/mosquitto/mosquitto.conf`, variável `apikey` da coleção e `API_KEY` do firmware (passo 1.2) |
| 2. O corpo do **grupo de serviço** | requisição **2.1** da coleção (passo 2.2) |
| 3. O corpo do **dispositivo** | requisição **2.2** da coleção (passo 2.3) |
| 4. O corpo da **subscrição do Cygnus** | requisição **4.1** da coleção (passo 4.1) |
| 5. O corpo da **notificação para o serviço externo** | requisição **4.4** da coleção (passo 4.2) |

Além disso, o grupo completa os **TODO do firmware** (Etapa 3) e monta o **painel** no Grafana (Etapa 4).

**Já vem pronto:**

- um **exemplo resolvido**: uma lâmpada inteligente simulada, com o simulador e todas as requisições prontas (seção *Exemplo resolvido*, entre as Etapas 1 e 2);
- o ambiente (`plataforma/docker-compose.yml`), o MySQL, o consumidor e a **ponte** com o broker público (você só troca a API key);
- **todas as outras requisições** da coleção: consultas, os comandos da Etapa 3 e a simulação de solo seco, marcadas com **[Pronto]**;
- as **verificações** de todas as etapas, marcadas com **[Verificação]**;
- o **reset do provisionamento** (pasta *0 - Recomeçar do zero* da coleção) e o **reset completo** (`docker compose down -v`, passo 1.7).

Nas 4 requisições marcadas com **[Complete o corpo]**, o método, a URL e os cabeçalhos já estão prontos: você escreve **só o corpo** (aba *Body*, JSON) e não altera o resto.

### 0.2 A pasta do projeto é o seu repositório

A pasta deste material é o repositório do grupo (`projeto2-<Nome>-<apikey>`). **Não altere a estrutura de pastas nem os nomes dos arquivos**: altere só o **conteúdo** dos arquivos marcados abaixo e acrescente o **relatório em PDF na raiz**.

```
projeto2-<Nome>-<apikey>/
├── README.md                          ← documentação do grupo (preencha o modelo)
├── relatorio.pdf                      ← VOCÊ ACRESCENTA: relatório técnico com R1 a R8
├── documentacao apoio/                (este guia, Material de apoio e o modelo do README)
├── firmware/
│   └── main_esqueleto.py              ← TODO 1 a 5 (na placa ou no Wokwi, grave como main.py)
├── plataforma/
│   ├── docker-compose.yml             (pronto)
│   ├── mosquitto/mosquitto.conf       ← a sua API key
│   ├── mysql/                         (pronto)
│   ├── servicos/                      (prontos: consumidor e lâmpada simulada do exemplo)
│   └── painel-estufa.json             ← VOCÊ ACRESCENTA: painel exportado do Grafana
└── postman/
    ├── Exemplo - Lâmpada.postman_collection.json  (pronta: exemplo resolvido)
    └── Projeto 2.postman_collection.json          ← variável apikey + 4 corpos
```

### 0.3 Arquitetura

```
              INTERNET                                        SEU COMPUTADOR (Docker)
 ┌──────────────┐        ┌───────────────────┐       ┌───────────────────────────────────────────────────────┐
 │ ESP32/Wokwi  │──MQTT──►                   │ ponte │ Mosquitto :1883 ◄──► IoT Agent JSON ──NGSI-v2──► Orion  │
 │ (estufa)     ◄────────┤ broker.hivemq.com ◄══════►  (só os tópicos       :4041            :1026 + MongoDB │
 └──────────────┘        │  (broker PÚBLICO) │       │   da SUA API key)                   subscrições │      │
 ┌──────────────┐        │                   │       │   consumidor :3001 ◄──────────────────────────┤      │
 │ HiveMQ Web   │◄──WSS──►                   │       │   Cygnus :5050 ◄──────────────────────────────┘      │
 │ Client/MQTTX │        └───────────────────┘       │     └──► MySQL :3306 ◄── Grafana :3000 (painel)        │
 └──────────────┘                                    └───────────────────────────────────────────────────────┘
                                                        ▲ Postman: provisionamento, comandos, consultas
```

| Tráfego | Caminho | Quem inicia |
| --- | --- | --- |
| **Norte** (medidas) | ESP32 → broker público → ponte → Mosquitto → IoT Agent → Orion → subscrições (Cygnus, consumidor) | a ESP32, a cada intervalo |
| **Sul** (comandos) | Postman → Orion → IoT Agent → Mosquitto → ponte → broker público → ESP32 → (resposta pelo caminho norte) | uma aplicação, pelo Orion |

O **IoT Agent é exatamente o das Aulas 8 e 9**: ele fala com o Mosquitto local. Quem decide o que entra e o que sai do broker público é a **ponte**, filtrada pela **API key** do grupo.

### 0.4 As etapas

| Etapa | O que você faz | Onde | Verificação |
| --- | --- | --- | --- |
| 1. Plataforma | Define a API key, sobe o FIWARE e testa a ponte | `plataforma/` | Teste da ponte + Postman, pasta *Etapa 1* |
| Exemplo resolvido | Roda e lê a lâmpada inteligente, toda pronta | `postman/Exemplo - Lâmpada...` | Coleção do exemplo verde no Runner |
| 2. Provisionamento | Corpos do grupo de serviço e do dispositivo; medida de teste | `postman/` + HiveMQ Web Client | Postman, pasta *Etapa 2* |
| 3. Firmware | Migra o firmware do Projeto 1 para os tópicos do IoT Agent | `firmware/main_esqueleto.py` | Postman, pasta *Etapa 3* |
| 4. Consumo do contexto | Corpos das duas subscrições e o painel no Grafana | `postman/` + Grafana | Postman, pasta *Etapa 4* |

### 0.5 Identificadores do projeto

| Item | Valor | Observação |
| --- | --- | --- |
| API key | definida pelo grupo | Letras e números, **única na turma**; maiúsculas e minúsculas contam. No broker público é ela que separa a sua estufa das outras. |
| `fiware-service` / `fiware-servicepath` | `fei` / `/estufa` | Mesmos valores no IoT Agent e no Orion (variáveis `servico` e `caminho` da coleção). |
| `device_id` | `estufa001` | O mesmo no provisionamento, na ponte e no firmware. |
| Entidade | `urn:ngsi-ld:Greenhouse:001`, tipo `Greenhouse` | Variável `entidade` da coleção. |
| Client id da ponte | `ponte_<API key>` | No broker público, todo client id precisa ser único. |
| Client id da ESP32 | `esp32_<API key>_<device_id>` | Já montado no esqueleto do firmware. |

Anote esses valores no `README.md` da raiz antes de começar.

---

## 1. Etapa 1 — Plataforma FIWARE e a ponte com o broker público

### 1.1 Pré-requisitos

- Docker Desktop aberto. **Encerre** os ambientes das Aulas 8 e 9 (`docker compose down` na pasta de cada uma): os contêineres têm os mesmos nomes e portas.
- Portas livres: 1026, 27017, 4041, 7896, 1883, 3000, 3001, 3306, 5050 e 5080.
- Postman.
- Um cliente MQTT para "enxergar" o broker público: o **HiveMQ WebSocket Client** (o do Projeto 1) ou o MQTTX.
- A estufa do Projeto 1: ESP32 real (Thonny) **ou** o projeto no **Wokwi**.
- Baixe as imagens **antes da aula** (cerca de 4 GB), dentro da pasta `plataforma`: `docker compose pull`.

> **Todos os comandos `docker compose` deste guia rodam dentro da pasta `plataforma`**, onde está o `docker-compose.yml`. Comece sempre com `cd plataforma`.

### 1.2 Defina a API key do grupo

Escolha uma API key **única na turma** (combine com os colegas ou acrescente alguns caracteres aleatórios) e coloque-a, **igual**, nos três lugares:

| Onde | O que trocar |
| --- | --- |
| `plataforma/mosquitto/mosquitto.conf` | `profRafael` → a sua API key no `remote_clientid` e nas 3 linhas `topic` |
| `postman/Projeto 2.postman_collection.json` | variável da coleção `apikey` (aba *Variables*, depois de importar no Postman) |
| `firmware/main_esqueleto.py` | constante `API_KEY` |

> **Não use `profRafael`.** É a API key de exemplo do professor. Duas estufas com a mesma API key misturam medidas e comandos (pergunta **R2**).

### 1.3 A ponte com o broker público

O arquivo `plataforma/mosquitto/mosquitto.conf` já vem pronto. Depois de trocar a API key, a ponte fica assim:

```
connection hivemq
address broker.hivemq.com:1883
remote_clientid ponte_<API key>
cleansession true
try_private false                 # não altere
notifications false               # não altere
bridge_protocol_version mqttv311  # não altere

topic /json/<API key>/estufa001/attrs  in  0
topic /json/<API key>/estufa001/cmdexe in  0
topic /<API key>/estufa001/cmd         out 0
```

Cada linha `topic` corresponde a um tópico do IoT Agent JSON (convenção da Aula 8):

| Tópico | Quem publica | Direção na ponte |
| --- | --- | --- |
| `/json/<apikey>/<device_id>/attrs` (medidas) | estufa, no broker público | `in`: do público para o local |
| `/json/<apikey>/<device_id>/cmdexe` (resultado dos comandos) | estufa, no broker público | `in` |
| `/<apikey>/<device_id>/cmd` (comandos) | IoT Agent, no broker local | `out`: do local para o público |

Só os tópicos da sua API key atravessam a ponte. Não altere as linhas `try_private`, `notifications` e `bridge_protocol_version`: o broker da HiveMQ recusa a ponte sem elas. O `docker-compose.yml` não precisa de alteração. Por que o IoT Agent não se conecta direto ao broker público? Veja a seção 3 do Material de apoio (pergunta **R1**).

### 1.4 Suba o ambiente

```bash
cd plataforma
docker compose up -d
docker compose ps                      # aguarde 9 contêineres "healthy" (o Cygnus leva ~20 s)
docker compose logs mosquitto          # estado da ponte (veja abaixo)
```

No log do Mosquitto:

- **`Connecting bridge hivemq (broker.hivemq.com:1883)`** aparece **uma vez** e não se repete: a ponte está conectada;
- a mesma linha **repetindo a cada poucos segundos**, seguida de `closed its connection`: o broker público recusou a ponte (client id repetido ou linhas obrigatórias alteradas);
- **`Error resolving bridge address`**: o endereço do broker está errado.

Mudou o `mosquitto.conf` com o ambiente no ar? `docker compose restart mosquitto`.

### 1.5 Teste a ponte nos dois sentidos

Deixe um terminal mostrando **todo** o tráfego do broker local. Ele é o seu "osciloscópio" do lado da plataforma:

```bash
docker exec -it mosquitto mosquitto_sub -v -t "#"
```

No **HiveMQ Web Client** (<https://www.hivemq.com/demos/websocket-client/>), clique em **Connect** e assine o tópico de **comandos** da sua estufa. Depois:

| # | Faça | Resultado esperado |
| --- | --- | --- |
| 1 | No Web Client, publique `oi` no tópico de **medidas** da sua estufa | aparece no terminal local |
| 2 | No Web Client, publique `oi` no mesmo tópico, trocando a API key por outra qualquer | **não** aparece no terminal local |
| 3 | Em outro terminal, publique no broker **local** no tópico de **comandos** da sua estufa: `docker exec mosquitto mosquitto_pub -t "<tópico>" -m oi` | aparece no Web Client |

O teste 1 ou o 3 falhou? Confira se a API key é a mesma no `mosquitto.conf` e no tópico que você usou.

### 1.6 Postman

1. Importe `postman/Projeto 2.postman_collection.json`.
2. Na coleção, aba **Variables**, preencha `apikey` com a sua API key e salve. Use `{{apikey}}` (e as demais variáveis) nos corpos que você escrever.
3. Rode a pasta **Etapa 1 - Ambiente** (botão *Run* na pasta). As requisições **[Verificação]** já estão prontas.

### ✅ Ponto de verificação 1

- [ ] `docker compose ps` mostra 9 contêineres `healthy` (inclusive a `lampada-simulada` do exemplo).
- [ ] A ponte conectou uma única vez (log do Mosquitto).
- [ ] Os 3 testes da ponte (passo 1.5) deram o resultado esperado.
- [ ] Todos os testes da pasta **Etapa 1** passam.

### 1.7 Como recomeçar do zero

Há dois níveis de reset:

| Reset | Como | O que apaga | O que fica |
| --- | --- | --- | --- |
| **Só o provisionamento** | pasta **0 - Recomeçar do zero** da coleção (pronta) | subscrições, dispositivo, entidade e grupo do seu caminho | histórico (MySQL) e painel (Grafana) |
| **Tudo** | `docker compose down -v` | os **serviços** (inclusive a lâmpada do exemplo) e os **volumes** deste compose: entidades, subscrições, grupos e dispositivos (MongoDB), histórico (MySQL), fonte de dados e painéis (Grafana) | nada: `docker compose up -d` sobe um ambiente limpo |

```bash
cd plataforma
docker compose down -v     # remove os serviços e os volumes deste compose
docker compose up -d       # ambiente limpo, como no primeiro dia
```

> Antes do `down -v`, **exporte o painel** do Grafana (passo 4.3). Sem o `-v`, o `docker compose down` para os serviços e **mantém** os dados.

---

## Exemplo resolvido — lâmpada inteligente

Antes de montar a estufa, veja um sistema **menor e completo** funcionando de ponta a ponta: uma lâmpada inteligente simulada, com o simulador, o provisionamento, os comandos e as duas subscrições **prontos**. Depois, você adapta cada peça para a estufa.

### E.1 A lâmpada inteligente simulada

A lâmpada sobe **junto com o ambiente** (`docker compose up -d`, passo 1.4): é o contêiner `lampada-simulada`.

```bash
cd plataforma
docker compose logs -f lampada-simulada      # medidas e comandos da lâmpada (Ctrl+C para sair)
```

| Item | Lâmpada |
| --- | --- |
| API key · caminho de serviço | `lampada2026` · `/lampada` |
| Dispositivo · entidade | `lampada001` · `urn:ngsi-ld:Lamp:001`, tipo `Lamp` |
| Medidas (`object_id` → atributo) | `s` → `state` (0 apagada, 1 acesa) · `l` → `luminosity` (% de luz no ambiente) |
| Comando | `setLight` (0 ou 1); responde `OK` ou `ERRO: <motivo>` |
| Estático | `name` |

- O simulador é `plataforma/servicos/lampada_simulada.py` (Python). Ele publica a cada 5 s e a luz do ambiente segue um "dia acelerado" (1 minuto real = 1 hora).
- A lâmpada fala com o Mosquitto **local**: não usa a ponte nem o broker público. Funciona sem internet (depois da primeira vez) e não colide com a lâmpada dos colegas. Até você rodar a coleção do exemplo, o IoT Agent recusa as medidas dela: é normal ver avisos da `lampada2026` no log do IoT Agent.
- Ela usa outra API key e outro caminho de serviço: **não interfere** na estufa. Use o mesmo IoT Agent, Orion, Cygnus e consumidor.

### E.2 Rode e leia o exemplo

1. Importe `postman/Exemplo - Lâmpada.postman_collection.json` e rode a **coleção inteira** no Runner (cerca de 1 min). Tudo deve ficar verde.
2. Leia, em cada requisição, o **corpo** e a **descrição**. Comece pelas 4 que você vai escrever para a estufa: **1.1** (grupo de serviço), **1.2** (dispositivo), **3.1** (subscrição do Cygnus) e **3.3** (notificação para o serviço externo).
3. Rode **2.1** de novo e acompanhe o comando e a resposta no log do simulador e no `mosquitto_sub` do passo 1.5.
4. Confira o histórico da lâmpada no MySQL:

```bash
docker exec -it db-mysql mysql -u root -pfei2026 fei -e "SELECT recvTime, attrName, attrValue FROM lampada ORDER BY CAST(recvTimeTs AS UNSIGNED) DESC LIMIT 6;"
```

| Pasta da coleção | O que mostra |
| --- | --- |
| 0 - Recomeçar do zero | reset do exemplo (só o caminho `/lampada`) |
| 1 - Provisionamento | grupo de serviço, dispositivo e o registro dos comandos |
| 2 - Comandos | comando válido e inválido: `_status` × `_info` |
| 3 - Subscrições | histórico no Cygnus e notificação para o consumidor |

Cada descrição termina com **Na estufa**: o que muda no seu caso.

### E.3 Da lâmpada para a estufa

| Você define | Lâmpada (pronto) | Estufa (você faz) |
| --- | --- | --- |
| API key | `lampada2026`, só no broker local | única na turma, na ponte, na coleção e no firmware |
| Corpo do grupo de serviço | tipo `Lamp` | tipo `Greenhouse` |
| Corpo do dispositivo | 2 medidas, 1 comando, estático `name` | 7 medidas, 4 comandos, estáticos `name` e `location` (`geo:json`) |
| Corpo da subscrição do Cygnus | `Lamp`, 2 medidas → tabela `lampada` | `Greenhouse`, 7 medidas → tabela `estufa` |
| Corpo da notificação externa | `state==1;luminosity>70` → `/alerta-lampada` | `soilMoisture` abaixo de 30 → `/alerta-estufa` |

**E o firmware?** Compare `lampada_simulada.py` (Python) com `firmware/main_esqueleto.py` (MicroPython): os três tópicos, o JSON de medidas com chaves curtas, o callback dos comandos e a resposta no `cmdexe` seguem a mesma lógica. A estufa acrescenta a validação de faixas, `setInterval`, `setSending` e o laço sem `time.sleep()`.

### ✅ Ponto de verificação do exemplo

- [ ] A coleção do exemplo roda inteira no Runner sem falhas.
- [ ] Você sabe dizer, para cada um dos 4 corpos, o que muda da lâmpada para a estufa.

---

## 2. Etapa 2 — Modelo de dados e provisionamento

### 2.1 O modelo da estufa

A estufa vira uma entidade `Greenhouse`. Os **nomes dos atributos** são fixos (as verificações, o histórico e o painel dependem deles). As **chaves curtas** do JSON (`object_id`) são escolha do grupo e devem ser documentadas no `README.md` da raiz.

**Medidas** (dispositivo → plataforma)

| Grandeza | Atributo NGSI | Tipo | Unidade / faixa |
| --- | --- | --- | --- |
| Temperatura do ar | `temperature` | Number | °C |
| Umidade relativa do ar | `relativeHumidity` | Number | % |
| Umidade do solo | `soilMoisture` | Number | % (0 = seco, 100 = encharcado), calibrada pelo grupo |
| Luminosidade | `illuminance` | Number | % (0 = escuro, 100 = claro), calibrada pelo grupo |
| Estado do relé | `relayState` | Number | 0 ou 1 |
| Ângulo da janela (servo) | `windowAngle` | Number | 0 a 180 |
| Intervalo de coleta | `samplingInterval` | Number | segundos (2 a 10) |

**Comandos** (plataforma → dispositivo): o que no Projeto 1 eram tópicos e mensagens agora são comandos NGSI.

| Projeto 1 | Projeto 2 (comando) | Valor | Efeito |
| --- | --- | --- | --- |
| tópico `/fei/<id>/rele` | `setRelay` | 0 ou 1 | desliga / liga o relé |
| tópico `/fei/<id>/servomotor` | `setServo` | 0 a 180 | posiciona a janela |
| `Atualizar:N` em `/fei/<id>/esp32` | `setInterval` | 2 a 10 | intervalo de coleta em segundos |
| `Ativar` / `Desativar` em `/fei/<id>/esp32` | `setSending` | 1 / 0 | ativa / desativa o envio das medidas |

A estufa responde **todo** comando com `"OK"` ou `"ERRO: <motivo>"`. Valor inválido **não muda** o estado.

**Atributos estáticos** (fixos, definidos no provisionamento)

| Atributo | Tipo | Valor |
| --- | --- | --- |
| `name` | Text | um nome para a estufa do grupo |
| `location` | geo:json | um `Point` com a localização da estufa (longitude, latitude) |

Antes de provisionar, **escreva no `README.md` da raiz** a tabela `object_id → atributo`. Você vai usá-la no firmware.

### 2.2 Corpo do grupo de serviço — requisição 2.1 [Complete o corpo]

A requisição já vem pronta: `POST http://{{iotagent}}/iot/groups`, com os cabeçalhos `fiware-service`, `fiware-servicepath` e `Content-Type`. Escreva **só o corpo**. Ele precisa definir:

- a **API key**: use `{{apikey}}`;
- o tipo de entidade `Greenhouse`;
- o recurso `/iot/json`;
- o Orion **visto de dentro da rede Docker** (quem acessa o Orion é o contêiner do IoT Agent);
- que dispositivos **não provisionados** sejam **rejeitados** (pergunta **R3**).

Consulte: Aula 8, README seção 8 (*API de provisionamento*). Os testes conferem o grupo **no IoT Agent**, não só a resposta da requisição.

### 2.3 Corpo do dispositivo — requisição 2.2 [Complete o corpo]

A requisição já vem pronta: `POST http://{{iotagent}}/iot/devices`, com os mesmos cabeçalhos. O corpo precisa definir:

- o `device_id` (`{{device_id}}`), a **API key** (`{{apikey}}`), a entidade (`{{entidade}}`) e o tipo `Greenhouse`;
- o transporte **MQTT**;
- os **7 atributos** de medida, cada um com o seu `object_id`, o nome NGSI e o tipo Number;
- os **4 comandos**;
- os **2 atributos estáticos** (`name` e `location`).

Os `object_id` precisam ser **os mesmos** do firmware.

### 2.4 Registro e medida de teste

1. Rode **2.3 [Pronto]**: ela consulta os registros no **Orion**. Quem atende os comandos da estufa? Consulte também a entidade: por que ela já existe, mas só com os comandos? (pergunta **R5**)
2. No HiveMQ WebSocket Client, assine **todos** os tópicos da sua API key (com o curinga `#`). Do lado do broker público, ele é o seu "osciloscópio" no resto do projeto; do lado da plataforma, o `mosquitto_sub` do passo 1.5.
3. Em **Publish**, publique **no tópico de medidas** da estufa um JSON com **uma ou duas** chaves suas e valores **numéricos**.
4. Confira a mensagem no terminal do `mosquitto_sub` (ela atravessou a ponte) e rode **2.4 [Verificação]** no Postman.

> A mensagem chegou ao terminal local, mas não ao Orion? O IoT Agent a recusou (`device_id`, corpo do provisionamento ou JSON): veja `docker compose logs iot-agent --tail 20`.

### ✅ Ponto de verificação 2

- [ ] Testes das requisições **2.1** a **2.4** passam.
- [ ] A tabela `object_id → atributo` está no `README.md` da raiz.
- [ ] Você sabe explicar por que, antes da medida de teste, a entidade no Orion só tinha os comandos.

---

## 3. Etapa 3 — Firmware da estufa

O circuito e os pinos são os do Projeto 1. O que muda é a comunicação. As requisições da Etapa 3 **já estão prontas**: elas enviam os comandos pelo Orion e conferem o resultado.

### 3.1 Prepare o firmware

1. Complete `firmware/main_esqueleto.py`. No repositório o nome do arquivo **não muda**; na ESP32 (Thonny) ou no Wokwi, grave o conteúdo como `main.py`.
2. Preencha `SSID`, `SENHA` e `API_KEY` (a mesma da ponte e da coleção). No Wokwi a rede é `Wokwi-GUEST`, sem senha.
3. Traga do Projeto 1 a leitura e a calibração dos sensores (`ler_sensores`, `TODO 2a`) e a conversão do servomotor.

> **Wokwi.** A ESP32 simulada acessa a internet e, portanto, o broker público: você consegue fazer o projeto inteiro sem a placa. Use o potenciômetro (ou o sensor que você usou no Projeto 1) para simular a umidade do solo.

> **Nunca no GitHub.** A senha do Wi-Fi **não** pode ir para o repositório. Troque por um valor de exemplo antes do *commit*.

### 3.2 Medidas: TODO 1 e TODO 2

1. **TODO 1:** os três tópicos, a partir de `API_KEY` e `DEVICE_ID`.
2. **TODO 2:** `ler_sensores()`, `publicar_medidas()` (UM JSON com as 7 medidas, chaves = seus `object_id`) e o laço principal.
3. Rode. Confira, nesta ordem:
   - o **Shell** mostra o JSON a cada 3 s, com números sem aspas;
   - o **HiveMQ Web Client** mostra as mensagens no tópico de medidas;
   - o `mosquitto_sub` local também mostra (atravessaram a ponte);
   - o Postman, requisição **3.1 [Pronto]**.

### 3.3 Comandos: TODO 3 e TODO 4

1. **TODO 3:** `setRelay` e `setServo` em `executar_comando()`, com validação.
2. **TODO 4:** o callback `ao_receber()` (resposta no tópico de resultado) e a assinatura do tópico de comandos.
3. Rode as requisições **3.2 a 3.7 [Pronto]**. Observe o comando e a resposta nos dois lados da ponte: no `mosquitto_sub` local e no HiveMQ Web Client.

> **Comandos são enviados pelo Orion**, nunca publicados à mão no broker. Se você publicar no tópico de comandos pelo Web Client, a ESP32 executa, mas o Orion não fica sabendo: é exatamente o que a plataforma existe para evitar.

### 3.4 Modos de operação: TODO 5

1. **TODO 5:** `setInterval` (2 a 10 s) e `setSending` (0/1).
2. Rode as requisições **3.8 a 3.15**, todas prontas. A verificação 3.13 leva cerca de 16 s: ela espera para provar que **nenhuma** medida chegou.

Requisitos que continuam valendo do Projeto 1: o laço principal **não** usa `time.sleep()` nem `wait_msg()`, e nenhuma mensagem inválida derruba o programa. Teste publicando `teste` no tópico de comandos pelo Web Client.

### ✅ Ponto de verificação 3

- [ ] Todos os testes da pasta **Etapa 3** passam com a estufa ligada.
- [ ] O checklist do fim de `main_esqueleto.py` está completo.
- [ ] A senha do Wi-Fi **não** está no repositório.

---

## 4. Etapa 4 — Consumo do contexto: histórico, alerta e painel

### 4.1 Corpo da subscrição do Cygnus — requisição 4.1 [Complete o corpo]

A requisição já vem pronta: `POST http://{{orion}}/v2/subscriptions`, com os cabeçalhos. O corpo precisa definir:

- as entidades do tipo `Greenhouse`;
- **só** os 7 atributos de medida;
- o endereço de notificação do **Cygnus**, visto por **quem envia** a notificação (o Orion, dentro da rede Docker);
- o formato que o Cygnus aceita.

Consulte: Aula 9, README seção 5. Depois rode **4.2** e **4.3 [Verificação]** e confira no terminal que as linhas estão chegando:

```bash
docker exec -it db-mysql mysql -u root -pfei2026 fei -e "SELECT recvTime, attrName, attrValue FROM estufa ORDER BY CAST(recvTimeTs AS UNSIGNED) DESC LIMIT 14;"
```

> Criou uma subscrição errada? **Apague-a** (pasta 0 da coleção ou `DELETE /v2/subscriptions/<id>`). Senão ela continua gravando ao lado da certa.

### 4.2 Corpo da notificação para o serviço externo — requisição 4.4 [Complete o corpo]

O serviço externo é o **consumidor** (`plataforma/servicos/consumidor.py`), que recebe os alertas. A requisição já vem pronta (`POST http://{{orion}}/v2/subscriptions`). O corpo precisa definir:

- a entidade da estufa;
- a condição: `soilMoisture` **abaixo de 30 %**, com uma expressão `q`;
- o destino: `http://consumidor:3000/alerta-estufa`;
- o formato `keyValues`, só com `soilMoisture`, `relayState` e `TimeInstant`;
- **sem** uma notificação a cada medida enquanto o solo estiver seco (Aula 7; Material de apoio, seção 6).

Depois rode **4.5 a 4.8** (prontas). A **4.7** simula uma medida de solo seco pela porta HTTP do IoT Agent. Em seguida, provoque o alerta **de verdade**: tire o sensor da terra (ou gire o potenciômetro no Wokwi) e acompanhe em <http://localhost:3001/notificacoes?caminho=/alerta-estufa>.

### 4.3 Painel no Grafana

1. Crie a fonte de dados MySQL com o usuário **somente leitura** (Aula 9, README seção 5, passo 4). Rode **4.9** e **4.10**.
2. Rode **4.11** para confirmar que o histórico da estufa está no MySQL.
3. Crie e salve um painel chamado exatamente **Estufa inteligente** com:
   - **a)** série temporal com temperatura **e** umidade do ar;
   - **b)** série temporal da umidade do solo;
   - **c)** linha do tempo (*State timeline*) do relé;
   - **d)** *Stat* ou *Gauge* com a luminosidade atual;
   - atualização automática (por exemplo, 5 s).
4. Rode **4.12** e **4.13**.
5. Exporte o painel (*Export → Export as code → Download file*) e salve como `plataforma/painel-estufa.json`.

Padrão de consulta para **uma** série (monte os outros painéis a partir dele):

```sql
SELECT CAST(recvTime AS DATETIME(3)) AS time,
       CAST(attrValue AS DECIMAL(6,1)) AS '<legenda>'
FROM estufa
WHERE attrName = '<atributo>' AND $__timeFilter(recvTime)
ORDER BY time;
```

Dicas da Aula 9: SQL no modo **Code**; formato *Time series*; `$__timeFilter(recvTime)` direto na coluna, nunca com `CAST` dentro; uma coluna `metric` separa as séries.

### 4.4 Fechando o ciclo

Com o painel aberto, ligue o relé (`setRelay` = 1) **pelo Orion** e observe: a resposta no Web Client, o `_status`/`_info` no Orion, a linha do tempo do relé no Grafana e, na estufa real, a umidade do solo subindo. Esse é o roteiro da demonstração final.

### ✅ Ponto de verificação 4

- [ ] Todos os testes da pasta **Etapa 4** passam.
- [ ] A **coleção inteira** roda no Runner, com a estufa ligada, sem falhas. A pasta **0 - Recomeçar do zero** apaga o provisionamento e as subscrições, e as requisições das etapas recriam tudo.
- [ ] O painel foi exportado em `plataforma/painel-estufa.json`.

---

## 5. Desafios (opcionais, contam como bônus)

| # | Desafio |
| --- | --- |
| D.1 | **Automação em malha fechada.** Um serviço (Python) recebe a notificação do alerta e liga a irrigação (`setRelay` = 1) **pelo Orion**; uma segunda subscrição desliga quando o solo passa de 60 %. Nada de MQTT no serviço. |
| D.2 | **Reconexão.** O broker público às vezes derruba conexões. Faça o firmware detectar a queda (`OSError` em `check_msg`/`publish`) e reconectar sozinho, assinando de novo o tópico de comandos. |
| D.3 | **TLS.** Leve a estufa e a ponte para a porta TLS do broker público. Discuta no relatório o que o TLS resolve e o que ele **não** resolve em um broker sem autenticação. |
| D.4 | **Segunda estufa.** Provisione `estufa002` (outra instância no Wokwi) no mesmo grupo, acrescente os tópicos dela na ponte e mostre as duas no painel, uma série por estufa. |

---

## 6. Entrega

### 6.1 O que entregar

A **pasta do projeto**, como repositório `projeto2-<Nome>-<apikey>`, com a **mesma estrutura** do material (seção 0.2):

- `README.md` da raiz preenchido (documentação do grupo, a partir do modelo). Inclua o link do projeto no Wokwi, se usar;
- `relatorio.pdf` **na raiz**: relatório técnico com objetivo, arquitetura, decisões de projeto e as respostas **R1 a R8**;
- a coleção exportada (Collection v2.1) por cima de `postman/Projeto 2.postman_collection.json` e o resultado do Runner em `postman/`;
- o painel em `plataforma/painel-estufa.json`;
- `firmware/main_esqueleto.py` completo, **sem** a senha do Wi-Fi;
- `plataforma/mosquitto/mosquitto.conf` com a sua API key.

### 6.2 Demonstração (roteiro sugerido, 5 min)

1. Ambiente no ar (`docker compose ps`) e a estufa publicando (Web Client + Orion).
2. Um comando de cada tipo **pelo Orion**, incluindo um inválido, mostrando `_status`/`_info`.
3. `setSending` = 0 e = 1.
4. Alerta de solo seco chegando ao consumidor.
5. Painel do Grafana reagindo a um comando.
6. Perguntas do professor sobre o caminho dos dados (R4 e R5).

---

## 7. Perguntas para o relatório

| # | Pergunta |
| --- | --- |
| R1 | O que é uma **assinatura compartilhada** (*shared subscription*)? O que aconteceria com a sua estufa, em uma turma de 20 grupos, se o IoT Agent de cada grupo se conectasse **direto** ao broker público? Explique como a ponte filtrada pela API key evita o problema e por que cada tópico da ponte tem a direção que tem. |
| R2 | Por que a API key precisa ser **única na turma**? O que aconteceria se dois grupos usassem a mesma API key e o mesmo `device_id`? |
| R3 | Por que o grupo deve **rejeitar** dispositivos não provisionados no broker público? Dê um exemplo do que poderia acontecer sem isso. |
| R4 | Descreva o caminho de **uma medida**, da ESP32 até o painel do Grafana: componente, protocolo, porta e formato do dado em cada salto. |
| R5 | Descreva o caminho de um `setRelay`, do Postman até o relé e de volta. Quando o `_status` fica `PENDING` e quando vira `OK`? Por que `OK` não garante que a estufa aceitou o comando (requisição 3.7)? |
| R6 | Por que `setSending` = 0 não pode desligar a escuta de comandos? |
| R7 | O que o Orion guarda e o que o MySQL guarda? Por que a subscrição do Cygnus usa `normalized` e a do alerta usa `keyValues`? |
| R8 | Qualquer pessoa conectada ao broker público pode ler e publicar nos seus tópicos. Descreva **dois ataques** possíveis à sua estufa e **duas medidas** que os evitariam em um sistema real. |

---

## 8. Problemas comuns

| Sintoma | Causa e solução |
| --- | --- |
| `docker compose` diz que não encontra o arquivo de configuração | Você não está na pasta `plataforma`. Rode `cd plataforma` antes. |
| `mosquitto` reiniciando ou *unhealthy* (e o IoT Agent não sobe) | Erro no `mosquitto.conf`: veja `docker compose logs mosquitto`. `Error resolving bridge address` = endereço do broker errado. |
| `Connecting bridge hivemq` repetindo a cada poucos segundos | O broker público recusou a ponte: outro cliente usa o mesmo `remote_clientid`, ou as linhas `try_private`/`notifications`/`bridge_protocol_version` foram alteradas. |
| A ponte não conecta e o endereço está certo | A rede pode bloquear a porta 1883 (algumas redes institucionais bloqueiam). Teste com o celular roteando a internet. |
| A medida aparece no Web Client, mas não no `mosquitto_sub` local | A API key do tópico é diferente da usada na ponte, ou o tópico não é o de medidas da `estufa001`. |
| A medida aparece no `mosquitto_sub` local, mas não no Orion | `device_id` diferente do provisionado (maiúsculas contam), corpo do provisionamento incompleto ou JSON inválido. Veja `docker compose logs iot-agent --tail 30`. |
| Teste de uma requisição **[Pronto]** falhou | A variável `apikey` é diferente da ponte e do firmware, ou os corpos 2.1/2.2 estão incompletos. |
| Atributos com nomes estranhos (`t`, `s`...) no Orion | A chave do JSON não corresponde a nenhum `object_id` provisionado: o IoT Agent repassa a chave como nome do atributo. Alinhe firmware e provisionamento. |
| Números aparecem como texto (`"25.3"`) | O firmware enviou string. Publique números sem aspas. |
| A ESP32 desconecta sozinha a cada poucos segundos | Outro cliente usa o **mesmo client id** no broker público (por exemplo, o seu firmware rodando no Wokwi **e** na placa). Rode só um, ou mude o `CLIENT_ID`. |
| Comando fica `PENDING` | A ESP32 não assinou o tópico de comandos, não respondeu no tópico de resultado ou a chave da resposta não é o nome exato do comando. Confira no `mosquitto_sub` local se o IoT Agent publicou o comando. |
| `_status` = `OK`, mas nada mudou | `OK` só confirma que a estufa respondeu. Leia o `<comando>_info`. |
| Medidas de **outra** estufa aparecem na sua entidade | Outro grupo usa a sua API key. Troque a API key na ponte, na coleção e no firmware, e reprovisione. |
| `lastSuccessCode` ≠ 200 na subscrição do Cygnus | `localhost` na URL (use o nome do serviço) ou `keyValues` (o Cygnus só aceita `normalized`). Veja `docker logs fiware-cygnus`. |
| O alerta não chega ao consumidor | A URL usa `localhost` ou a porta do seu computador (3001). Quem notifica é o Orion, de dentro da rede Docker. |
| O Grafana não conecta ao MySQL | Use `mysql-db:3306`, banco `fei`, usuário `grafana`/`grafana2026`. |
| Porta 3306 ocupada | Já existe um MySQL no computador. Use `"3307:3306"` no `docker-compose.yml`. |
| `lampada-simulada` reiniciando | Sem internet para instalar o `paho-mqtt` na primeira vez. Veja `docker compose logs lampada-simulada`. |
| A coleção do exemplo falha na 1.4 | A `lampada-simulada` não está `healthy`: veja `docker compose ps` e `docker compose logs lampada-simulada`. |
| Nada mais faz sentido | Recomece do zero (passo 1.7): `docker compose down -v` e `docker compose up -d`. |

---

## 9. Referências

- Aula 5 — Conectividade ESP32 e MQTT (laço não bloqueante, `umqtt.simple`).
- Aula 6 e Aula 7 — Orion: entidades, consultas, registros e subscrições.
- Aula 8 — IoT Agent JSON: provisionamento, tópicos e comandos (README seções 5, 6 e 8).
- Aula 9 — Cygnus, MySQL e Grafana (README seções 5, 6 e 7).
- FIWARE IoT Agent JSON: <https://fiware-iotagent-json.readthedocs.io>
- FIWARE Orion (NGSI-v2): <https://fiware-orion.readthedocs.io>
- HiveMQ MQTT Essentials (inclui *shared subscriptions*): <https://www.hivemq.com/mqtt/>
