# Estufa inteligente na plataforma FIWARE — Grupo `<apikey>`

> Modelo de documentação do repositório do Projeto 2 (CCM520 – Internet das Coisas). Substitua tudo o que está entre `< >` e apague as instruções em itálico. O objetivo é que **outra pessoa consiga reproduzir o projeto** só com este README.

**Integrantes:** `<nome (RA)>`, `<nome (RA)>`
**Link do Wokwi (se usar):** `<link>`
**Vídeo da demonstração (opcional):** `<link>`

## 1. Descrição

_Em um parágrafo: o que a estufa monitora, o que ela aciona e como a plataforma FIWARE entra no sistema._

## 2. Arquitetura

_Um diagrama (imagem ou ASCII) com a ESP32, o broker público, o IoT Agent, o Orion, o Cygnus/MySQL, o Grafana e o consumidor. Indique protocolo e porta em cada ligação._

## 3. Hardware

| Componente | Pino da ESP32 | Observação |
| --- | --- | --- |
| DHT22 | `<GPIO>` | |
| Umidade do solo | `<GPIO>` | |
| LDR | `<GPIO>` | |
| Relé | `<GPIO>` | |
| Servomotor | `<GPIO>` | |

**Calibração:** _como vocês converteram as leituras do ADC em % de umidade do solo e de luminosidade (valores de referência medidos)._

## 4. Identificadores

| Item | Valor |
| --- | --- |
| API key | `<...>` |
| Client id da ponte | `<...>` |
| `fiware-service` / `fiware-servicepath` | `fei` / `/estufa` |
| `device_id` | `estufa001` |
| Entidade | `urn:ngsi-ld:Greenhouse:001` (`Greenhouse`) |
| Client id MQTT da ESP32 | `<...>` |

## 5. Modelo de dados

### 5.1 Medidas

| `object_id` (firmware) | Atributo NGSI | Tipo | Unidade / faixa |
| --- | --- | --- | --- |
| `<...>` | `temperature` | Number | °C |
| `<...>` | `relativeHumidity` | Number | % |
| `<...>` | `soilMoisture` | Number | % |
| `<...>` | `illuminance` | Number | % |
| `<...>` | `relayState` | Number | 0/1 |
| `<...>` | `windowAngle` | Number | 0–180 |
| `<...>` | `samplingInterval` | Number | s |

Exemplo de payload publicado: `<...>`

### 5.2 Comandos

| Comando | Valores aceitos | Resposta de sucesso | Respostas de erro |
| --- | --- | --- | --- |
| `setRelay` | `<...>` | `OK` | `<...>` |
| `setServo` | `<...>` | `OK` | `<...>` |
| `setInterval` | `<...>` | `OK` | `<...>` |
| `setSending` | `<...>` | `OK` | `<...>` |

### 5.3 Tópicos MQTT

| Sentido | Tópico |
| --- | --- |
| Medidas | `<...>` |
| Comandos | `<...>` |
| Resultado | `<...>` |

### 5.4 Ponte com o broker público

| Padrão | Direção | Por quê |
| --- | --- | --- |
| `<...>` | `in` | `<...>` |
| `<...>` | `out` | `<...>` |

## 6. Como reproduzir

_Passo a passo numerado, do `git clone` até o painel funcionando: `mosquitto.conf` (ponte), `docker compose up -d`, teste da ponte, importação da coleção, ordem das requisições, gravação do firmware, criação da fonte de dados e do painel. Informe o que o leitor deve ver ao final de cada passo._

## 7. Subscrições

| Subscrição | Condição | Destino | Atributos e formato | Por que assim |
| --- | --- | --- | --- | --- |
| Histórico | `<...>` | `<...>` | `<...>` | `<...>` |
| Alerta de solo seco | `<...>` | `<...>` | `<...>` | `<...>` |

## 8. Painel

_Captura de tela do painel "Estufa inteligente" e uma linha sobre cada visualização (consulta usada e o que ela mostra). O JSON exportado está em `plataforma/painel-estufa.json`._

## 9. Testes

_Captura do Runner do Postman com a coleção inteira passando (pasta 99 antes) e o arquivo de resultados exportado em `postman/`._

## 10. Decisões de projeto e limitações

_O que vocês escolheram e por quê (calibração, validação dos comandos, tratamento de falhas), o que não funciona bem e o que fariam diferente em um sistema real (pense no broker público)._

## 11. Desafios realizados

_Quais desafios (D.1 a D.4) foram feitos e onde estão no repositório._

## 12. Uso de ferramentas de IA

_Declare, conforme as regras de integridade acadêmica da disciplina, em que partes usaram modelos de linguagem e para quê (por exemplo: explicação de um erro, revisão do texto)._

## 13. Referências

_Material das aulas, documentação do FIWARE e da HiveMQ, e qualquer outra fonte consultada._
