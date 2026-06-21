# Importação de Dados Históricos para o Prometheus

Script para converter arquivos CSV (exportados de outra plataforma) para o formato OpenMetrics e importá-los no Prometheus, mantendo compatibilidade com o dashboard Grafana existente.

## Estrutura dos CSVs

Os arquivos CSV devem estar na pasta `historical_data/` com dados do inversor contendo a coluna `Updated Time` como timestamp. Exemplo de nome: `202601.csv`, `202602.csv`, etc.

## O que o script faz

O `csv_to_openmetrics.py` lê todos os CSVs em `historical_data/` e mapeia as colunas para as mesmas métricas Prometheus que o `InverterData.py` exporta em tempo real:

| Coluna CSV | Métrica Prometheus |
|---|---|
| DC Voltage PV1(V) | `SolarVoltage_volts{Voltage="PV1"}` |
| DC Voltage PV2(V) | `SolarVoltage_volts{Voltage="PV2"}` |
| DC Current PV1(A) | `SolarCurrent_ampers{Current="PV1"}` |
| DC Current PV2(A) | `SolarCurrent_ampers{Current="PV2"}` |
| DC Power PV1(W) | `SolarPower{Power="PV1"}` |
| DC Power PV2(W) | `SolarPower{Power="PV2"}` |
| Total AC Output Power(W) | `OutputPower_watts{Power="Active"}` |
| AC Output Frequency R(Hz) | `OutputFreq{Grid="Frequency"}` |
| AC Voltage R/U/A(V) | `OutputVoltage_volts{Voltage="L1"}` |
| AC Current R/U/A(A) | `OutputCurrent_ampers{Current="L1"}` |
| Cumulative Production (Active)(kWh) | `SolarProduction_watts_total{Production="Total"}` |
| Daily Production (Active)(kWh) | `SolarProduction_watts_total{Production="Today"}` |
| Generation Time Today(Min) | `SolarTime{GenerationTime="Today"}` |
| Generation Time Total(Min) | `SolarTime{GenerationTime="Total"}` |
| Single Plate Ambient Temperature(℃) | `InverterTemp_celsius{Temp="Ambient"}` |
| Radiator Temperature 1(℃) | `InverterTemp_celsius{Temp="Inner"}` |
| Bus Voltage(V) | `InverterVoltage_volts{Voltage="Bus"}` |

## Como usar

### 1. Gerar o arquivo OpenMetrics

```bash
python3 csv_to_openmetrics.py
```

Isso cria o arquivo `openmetrics_output.txt` na raiz do projeto.

### 2. Baixar o promtool

O `promtool` vem junto com o Prometheus. Se não tiver instalado localmente:

```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.53.0/prometheus-2.53.0.linux-amd64.tar.gz
tar xzf prometheus-2.53.0.linux-amd64.tar.gz
```

### 3. Criar os blocos TSDB

```bash
./promtool tsdb create-blocks-from openmetrics openmetrics_output.txt /path/to/prometheus/data
```

Para descobrir o path de dados do Prometheus rodando em Docker:

```bash
docker inspect prometheus | grep -i mount
```

### 4. Reiniciar o Prometheus

```bash
docker restart prometheus
```

## Resultado

Após o restart, os dados históricos estarão disponíveis no Prometheus e Grafana com as mesmas métricas e labels que o `InverterData.py` exporta em tempo real. O dashboard Grafana funciona sem alterações.

## Observações

- O timezone dos timestamps é `America/Sao_Paulo` (configurável no script)
- Apenas arquivos `2*.csv` são processados (ignora outros formatos como o Daily Statistics)
- Valores não numéricos ou linhas sem timestamp são ignorados automaticamente
