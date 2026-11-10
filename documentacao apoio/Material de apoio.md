# Projeto 2 — Material de apoio

**CCM520 – Internet das Coisas** · Centro Universitário FEI

Este material explica os **conceitos** que o Projeto 2 usa e que não estavam em primeiro plano nas aulas: o broker público, a assinatura compartilhada do IoT Agent e a ponte MQTT que resolve o problema, o ciclo de vida de um comando e os cuidados com subscrições, histórico e segurança. Ele **não** traz os corpos das requisições nem o firmware prontos: para o passo a passo, use o `README.md` desta pasta (guia) e o material das Aulas 5 a 9.

---

## 1. Do Projeto 1 ao Projeto 2

| Aspecto | Projeto 1 | Projeto 2 |
| --- | --- | --- |
| Quem manda comandos | você, pelo HiveMQ WebSocket Client | qualquer aplicação, **pelo Orion** (NGSI-v2) |
| Quem conversa com a ESP32 | você | o **IoT Agent JSON**, através de uma **ponte** MQTT |
| Tópicos | `/fei/<id>/<grandeza>`, um por grandeza | convenção do IoT Agent: medidas, comandos e resultado |
| Payload das medidas | um valor por tópico | **um JSON** com todas as medidas (chaves = `object_id`) |
| Resposta a comandos | não havia | obrigatória, no tópico de resultado |
| `Ativar` / `Desativar` / `Atualizar:N` | mensagens no tópico `esp32` | comandos `setSending` e `setInterval` |
| Estado atual | só quem estava assinando via | a entidade no **Orion** |
| Histórico | não havia | **Cygnus → MySQL**, visto no **Grafana** |
| Broker | `broker.hivemq.com:1883` | o **mesmo** para a ESP32; o IoT Agent usa um Mosquitto local ligado a ele por uma ponte |

A ideia central: a ESP32 deixa de ser "um dispositivo que alguém comanda pelo MQTT" e vira **uma entidade de contexto**. Quem a usa não precisa saber que existe MQTT, qual é o tópico ou qual é o broker.

---

## 2. O broker público

`broker.hivemq.com` é um broker de demonstração mantido pela HiveMQ, aberto a qualquer pessoa.

| Porta | Protocolo | Uso no projeto |
| --- | --- | --- |
| 1883 | MQTT sobre TCP, sem criptografia | ESP32 e a ponte do Mosquitto local |
| 8883 | MQTT sobre TLS | desafio D.3 |
| 8000 / 8884 | MQTT sobre WebSocket / WebSocket seguro | HiveMQ WebSocket Client (navegador) |

**O que "público" significa na prática**

- **Não há autenticação.** Qualquer cliente conecta, sem usuário e senha.
- **Não há controle de acesso por tópico.** Qualquer cliente pode **assinar** `#` e ver todas as mensagens, inclusive as suas, e **publicar** em qualquer tópico, inclusive nos seus.
- **O espaço de tópicos é de todos.** Dois grupos que escolherem os mesmos tópicos vão misturar as mensagens. No Projeto 2 a **API key** faz o papel do "sobrenome" dos tópicos: por isso ela precisa ser única.
- **O client id é exclusivo.** Se dois clientes conectam com o mesmo id, o broker desconecta o mais antigo. Dois programas com o mesmo id ficam derrubando um ao outro em ciclo, o que parece "o broker está instável".
- **Não há garantia de serviço.** Conexões caem, e mensagens com QoS 0 podem se perder. Em um sistema real você teria um broker próprio (como o Mosquitto das Aulas 8 e 9) ou um serviço gerenciado com autenticação.

**Por que usá-lo então?** Porque a estufa (real ou no **Wokwi**) e a plataforma estão em redes diferentes. O Wokwi, por exemplo, não alcança o Mosquitto do seu computador, mas alcança a internet. O broker público é o ponto de encontro mais simples, e os problemas que ele cria são, eles mesmos, parte do aprendizado.

---

## 3. Por que o IoT Agent não se conecta direto ao broker público

### 3.1 Assinatura normal × compartilhada

```
 ASSINATURA NORMAL                          ASSINATURA COMPARTILHADA ($share/<grupo>/<filtro>)
 todos os assinantes recebem tudo           o broker DIVIDE as mensagens entre os membros do grupo

 publicador ─► m1 m2 m3 ─► broker           publicador ─► m1 m2 m3 ─► broker
                           ├─► A: m1 m2 m3                            ├─► A: m1    m3
                           └─► B: m1 m2 m3                            └─► B:    m2
```

Uma assinatura compartilhada tem a forma `$share/<nome-do-grupo>/<filtro>`. O broker trata todos os clientes com o mesmo `<nome-do-grupo>` e o mesmo `<filtro>` como **um único assinante lógico** e entrega cada mensagem a **apenas um** deles. Isso serve para **balancear carga**: várias cópias de um mesmo serviço repartem o trabalho.

### 3.2 O que isso tem a ver com o IoT Agent

O IoT Agent JSON 3.x **não** assina os tópicos de cada dispositivo. Ele assina **curingas**, dentro de uma assinatura compartilhada com o nome de grupo **fixo** `json`:

```
$share/json//+/+/attrs        $share/json//json/+/+/attrs        $share/json//json/+/+/cmdexe   ...
```

Com um broker **privado** isso é ótimo: se você tiver três réplicas do IoT Agent, elas dividem as medidas. Em um broker **público**, porém, **todos** os IoT Agents conectados (os da turma inteira e os de qualquer pessoa no mundo) entram no mesmo grupo, com o mesmo filtro. **Usar API keys diferentes não resolve**: os tópicos das estufas são diferentes, mas todos casam com o mesmo curinga, e o broker entrega cada medida a um agente qualquer do grupo, que a descarta se não conhecer a API key.

Teste feito no `broker.hivemq.com` durante a preparação do projeto: dois "IoT Agents" (A e B) assinaram `$share/json//json/+/+/attrs`, cada um dono de uma API key diferente, e cada estufa publicou 20 medidas. Um terceiro cliente assinou o mesmo filtro **sem** `$share`, como controle.

| Rodada | A recebeu da própria estufa | B recebeu da própria estufa | Controle |
| --- | --- | --- | --- |
| 1 | 16 de 20 | 16 de 20 | 40 de 40 |
| 2 | 20 de 20 | **0 de 20** | 40 de 40 |
| 3 | 20 de 20 | **0 de 20** | 40 de 40 |

Não há variável de ambiente no IoT Agent 3.14 para mudar o nome do grupo.

### 3.3 A solução do projeto: uma ponte filtrada pela API key

Uma **ponte** (*bridge*) é uma conexão de um broker com outro: o Mosquitto local se conecta ao broker público **como cliente** e repassa as mensagens dos padrões que você configurar, em cada direção.

```
 broker PÚBLICO                         ponte (no Mosquitto local)                 broker LOCAL
 ESP32 publica e assina   ── in  ──►  traz só os padrões "in"             ──►   IoT Agent assina ($share/json)
                          ◄── out ──  leva só os padrões "out"            ◄──   IoT Agent publica comandos
```

- O IoT Agent fica **igual ao das Aulas 8 e 9**, conectado ao Mosquitto local. Lá ele é o **único** membro do grupo `json`, então recebe tudo.
- A ponte assina no broker público **somente** os padrões da **sua API key**: as estufas dos outros grupos nem chegam ao seu computador. É a API key que controla o que atravessa.
- Cada linha `topic` do `mosquitto.conf` tem um padrão e uma direção. Para escolher, pergunte: **quem publica** esse tópico, e **onde** está quem precisa recebê-lo?
- Com as opções padrão do Mosquitto, o broker da HiveMQ recusa a ponte, que fica conectando e desconectando. As três linhas fixas do `mosquitto.conf` resolvem: `try_private false` desliga uma extensão do Mosquitto que outros brokers não precisam entender, `notifications false` desliga a mensagem de estado que a ponte publicaria em `$SYS/...` (tópicos `$` são reservados ao broker) e `bridge_protocol_version mqttv311` fixa a versão do protocolo.
- Sem o `try_private`, o Mosquitto não consegue evitar **laços**. Por isso use **um padrão `in` e um padrão `out`**, nunca a direção `both`, e nunca o padrão `#` sozinho (ele traria o broker público inteiro).

> **Experimento opcional.** No MQTTX, conecte dois clientes ao broker público que assinam `$share/<algo-seu>/teste/<seu-id>` e um terceiro que publica 10 mensagens em `teste/<seu-id>`. Observe quem recebe o quê. Repita sem o `$share/...`.

---

## 4. IoT Agent JSON aplicado à estufa

### 4.1 Grupo × dispositivo

| Objeto | Responde à pergunta | Campos principais |
| --- | --- | --- |
| **Grupo** (`/iot/groups`) | "Que API key é aceita, para qual tipo de entidade e para qual Orion?" | `apikey`, `entity_type`, `resource`, `cbroker`, `autoprovision` |
| **Dispositivo** (`/iot/devices`) | "Este `device_id` vira qual entidade, com quais atributos e comandos?" | `device_id`, `apikey`, `entity_name`, `entity_type`, `transport`, `attributes`, `commands`, `static_attributes` |

- `autoprovision` decide o que acontece quando chega uma medida de um `device_id` **não provisionado** com uma API key válida. Pense no que isso significa em um broker onde **qualquer um** publica.
- `cbroker` é o endereço do Orion **para o IoT Agent**, que roda dentro da rede Docker.
- Os cabeçalhos `fiware-service` e `fiware-servicepath` do provisionamento definem onde a entidade vai morar no Orion.

### 4.2 Da chave curta ao atributo

O firmware publica chaves curtas para economizar bytes. O provisionamento diz como traduzi-las:

```
 firmware publica  {"<chave1>": 24.8, "<chave2>": 61}
                          │                 │
 provisionamento   object_id → name   object_id → name
                          ▼                 ▼
 entidade no Orion  temperature = 24.8   relativeHumidity = 61
```

- Uma chave que **não** é `object_id` de nenhum atributo é repassada **com o próprio nome**. É por isso que um erro de digitação no firmware cria um atributo estranho no Orion em vez de dar erro.
- Com `IOTA_TIMESTAMP=true`, o IoT Agent acrescenta o atributo `TimeInstant` e o metadado `TimeInstant` em **cada** atributo atualizado.
- Logo após o provisionamento a entidade já existe, mas só com os **comandos**. Os atributos de medida aparecem na primeira medida.

### 4.3 O ciclo de vida de um comando

```
 Postman            Orion                  IoT Agent                 broker público          ESP32
    │ PATCH setRelay=1 │                        │                          │                    │
    │─────────────────►│ registro: quem atende  │                          │                    │
    │                  │ setRelay? → IoT Agent  │                          │                    │
    │                  │───────────────────────►│ setRelay_status=PENDING  │                    │
    │◄── 204 ──────────│                        │── publica comando ──────►│───────────────────►│
    │                  │                        │                          │   executa e        │
    │                  │                        │◄── resultado ────────────│◄── responde ───────│
    │                  │◄── setRelay_status=OK, │                          │                    │
    │                  │    setRelay_info=<resposta>                       │                    │
```

- O `204` do Orion só diz que o pedido foi **encaminhado**. Ninguém garante, nesse momento, que a estufa existe ou está ligada.
- `<comando>_status` diz em que pé está a **entrega**: `PENDING` (enviado, sem resposta) ou `OK` (a estufa respondeu).
- `<comando>_info` traz **o que a estufa respondeu**. É aí que aparece `ERRO: ...`.
- A chave da resposta precisa ser **exatamente** o nome do comando. Se não for, o IoT Agent não sabe a que comando ela se refere, e o `_status` fica `PENDING`.

---

## 5. Firmware: padrões úteis em MicroPython

| Situação | Padrão |
| --- | --- |
| Montar o JSON | `json.dumps({...})`. Números Python viram números JSON. Nunca concatene strings para montar JSON. |
| Ler o comando | `json.loads(mensagem)` dentro de `try/except ValueError`. O resultado pode não ser um dicionário: confira com `isinstance`. |
| Validar um valor | `int(valor)` dentro de `try/except (TypeError, ValueError)`, e só **depois** confira a faixa. Mude o estado apenas se tudo deu certo. |
| Tempo sem bloquear | `time.ticks_ms()` e `time.ticks_diff(agora, antes) >= intervalo`, como na Aula 5. |
| DHT22 | `measure()` pode lançar `OSError`. Trate e descarte só aquela medida. |
| Memória | `gc.collect()` de vez em quando no laço. |
| Depurar | `print()` do que você publica e do que recebe. O Shell (Thonny ou Wokwi) e o HiveMQ Web Client, lado a lado, mostram onde a mensagem parou. |

**Wokwi**

- Rede `Wokwi-GUEST`, sem senha. A simulação acessa a internet, então alcança o broker público.
- O DHT22 do Wokwi deixa você mudar temperatura e umidade clicando no componente durante a simulação.
- Um potenciômetro no pino do sensor de solo permite simular solo seco e úmido (útil para o alerta).
- Não rode o mesmo firmware no Wokwi **e** na placa ao mesmo tempo: o client id é o mesmo.

---

## 6. Subscrições para a estufa

| Campo | Para que serve |
| --- | --- |
| `subject.entities` | Quais entidades (por `id` ou `idPattern`, e `type`). |
| `subject.condition.attrs` | Quais atributos, ao mudar, fazem o Orion **avaliar** a subscrição. Vazio = qualquer atributo. |
| `subject.condition.expression.q` | Filtro sobre o **novo** estado: `soilMoisture<30`, `temperature>35`, `relayState==1`. Use `;` para "e". |
| `notification.http.url` | Para onde o **Orion** envia. Use nomes da rede Docker (`cygnus`, `consumidor`), nunca `localhost`. |
| `notification.attrs` | Quais atributos vão na notificação. Vazio = todos. |
| `notification.attrsFormat` | `normalized` (com tipo e metadados, exigido pelo Cygnus) ou `keyValues` (só os valores, mais fácil para um serviço simples). |
| `throttling` | Intervalo mínimo, em segundos, entre duas notificações da mesma subscrição. |

**Cuidado com o `TimeInstant`.** Cada medida muda o metadado `TimeInstant` de **todos** os atributos, mesmo que o valor seja o mesmo. Para o Orion, isso é uma mudança. Uma subscrição de alerta sem cuidado dispara **a cada medida** enquanto a condição for verdadeira: com a estufa publicando a cada 3 s, são 20 alertas por minuto. Pense em como limitar isso.

**Texto proibido.** O Orion recusa `( ) < > " ' = ;` em textos como `description`. Uma descrição como `Alerta (solo < 30%)` gera *forbidden characters*. Repare que a expressão `q` aceita `<` e `;`, porque é sintaxe e não texto livre.

---

## 7. Histórico e painel

Com `dm-by-service-path` e `row`, o Cygnus grava uma linha por atributo notificado na tabela com o nome do caminho de serviço, sem a barra: `/estufa` vira a tabela **`estufa`** do banco **`fei`**.

| Coluna | Conteúdo |
| --- | --- |
| `recvTimeTs` / `recvTime` | instante em que o Cygnus recebeu (ms / texto em UTC) |
| `entityId`, `entityType` | a estufa |
| `attrName`, `attrType`, `attrValue` | o atributo, o tipo e o valor, **como texto** |
| `attrMd` | metadados, incluindo o `TimeInstant` da medida |

Uma medida da estufa com 7 atributos gera **7 linhas**. Todas as colunas são texto: converta com `CAST`.

**Padrão de consulta para uma série temporal no Grafana** (troque `<atributo>` e monte os outros painéis a partir dele):

```sql
SELECT CAST(recvTime AS DATETIME(3)) AS time,
       CAST(attrValue AS DECIMAL(6,1)) AS '<legenda>'
FROM estufa
WHERE attrName = '<atributo>' AND $__timeFilter(recvTime)
ORDER BY time;
```

- Duas grandezas no mesmo gráfico: duas consultas (A e B) no mesmo painel, ou uma coluna `metric` com o nome do atributo.
- Último valor (*Stat*, *Gauge*): formato *Table* e `ORDER BY CAST(recvTimeTs AS UNSIGNED) DESC LIMIT 1`.
- *State timeline* do relé: devolva texto (`IF(attrValue = '1', 'ligado', 'desligado')`) e defina as cores em *Value mappings*.
- Não coloque `CAST(...)` dentro de `$__timeFilter`.

---

## 8. Segurança: o que o broker público não oferece

Pense na estufa pelas três propriedades clássicas de segurança da informação:

| Propriedade | Pergunta | No broker público, porta 1883 |
| --- | --- | --- |
| **Confidencialidade** | Quem consegue **ler** os dados? | Todos que assinarem os tópicos certos (ou `#`). O tráfego também passa em texto puro pela rede. |
| **Integridade** | Quem consegue **alterar ou forjar** dados? | Todos que conhecerem os tópicos, que estão visíveis para quem assina `#`. |
| **Disponibilidade** | Quem consegue **impedir** o sistema de funcionar? | Todos que souberem o client id dos seus clientes ou que inundarem os seus tópicos. |

Recursos que mudam esse quadro em um sistema real: broker próprio ou gerenciado, autenticação (usuário/senha ou certificado por dispositivo), listas de controle de acesso por tópico (ACL), TLS e o IoT Agent também protegido. Para a pergunta R8, relacione cada ataque que você descrever a uma dessas propriedades e escolha o recurso que o impede. Cuidado: alguns recursos protegem uma propriedade e não as outras.

---

## 9. Cola rápida

### Endereços

| Serviço | Do seu computador (Postman, navegador) | De dentro da rede Docker |
| --- | --- | --- |
| Orion | `localhost:1026` | `orion:1026` |
| IoT Agent (provisionamento) | `localhost:4041` | `iot-agent:4041` |
| IoT Agent (medidas HTTP) | `localhost:7896` | `iot-agent:7896` |
| Consumidor | `localhost:3001` | `consumidor:3000` |
| Cygnus (notificações / gestão) | `localhost:5050` / `localhost:5080` | `cygnus:5050` |
| MySQL | `localhost:3306` | `mysql-db:3306` |
| Grafana | `localhost:3000` | `grafana:3000` |
| Mosquitto (broker local) | `localhost:1883` | `mosquitto:1883` |
| Broker MQTT público | `broker.hivemq.com:1883` | (só a ponte se conecta a ele) |

### Requisições que você vai usar

| Para quê | Requisição |
| --- | --- |
| Grupos | `POST` / `GET` / `DELETE /iot/groups` (IoT Agent) |
| Dispositivos | `POST /iot/devices`, `GET` / `PUT` / `DELETE /iot/devices/<device_id>` (IoT Agent) |
| Estado atual | `GET /v2/entities/<id>` com `options=keyValues` e `attrs=...` (Orion) |
| Comando | `PATCH /v2/entities/<id>/attrs` com o comando do tipo `command` (Orion) |
| Registros | `GET /v2/registrations` (Orion) |
| Subscrições | `POST` / `GET` / `DELETE /v2/subscriptions` (Orion) |

Todas as requisições ao IoT Agent e ao Orion levam `fiware-service: fei` e `fiware-servicepath: /estufa`.

### Glossário

| Termo | Significado |
| --- | --- |
| API key | Chave do grupo de provisionamento. Aparece nos tópicos e separa os dispositivos de grupos diferentes. |
| `object_id` | Chave curta que o dispositivo publica; o provisionamento a traduz para o nome do atributo. |
| Tráfego norte / sul | Do dispositivo para a plataforma (medidas) / da plataforma para o dispositivo (comandos). |
| Registro | Aviso do IoT Agent ao Orion: "os comandos desta entidade são comigo". |
| Subscrição | Pedido ao Orion: "me avise quando isto mudar". |
| *Shared subscription* | Assinatura MQTT em que o broker divide as mensagens entre os membros de um grupo. |
| Ponte (*bridge*) | Conexão de um broker com outro que repassa os tópicos configurados, em cada direção. |
