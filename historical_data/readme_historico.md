# Importação de Dados Históricos para o Prometheus

Scripts para converter arquivos CSV (exportados da plataforma Solarman) para o formato OpenMetrics e importá-los no Prometheus, mantendo compatibilidade com o dashboard Grafana.

## Estrutura

```
historical_data/
├── csv_to_openmetrics.py       # Converte CSVs → OpenMetrics
├── import_to_prometheus.py     # Importa via Remote Write API
├── readme_historico.md         # Este arquivo
├── 202512.csv                  # Dados mensais exportados
├── 202601.csv
├── ...
└── openmetrics_output.txt      # Gerado pelo script (não commitar)
```

## Passo 1: Gerar arquivo OpenMetrics

```bash
cd historical_data/
python3 csv_to_openmetrics.py
```

Lê todos os arquivos `2*.csv` da pasta e gera `openmetrics_output.txt` com as métricas no formato que o Prometheus aceita.

### Métricas mapeadas

| Coluna CSV | Métrica Prometheus |
|---|---|
| DC Voltage PV1/PV2(V) | `SolarVoltage_volts{Voltage="PV1/PV2"}` |
| DC Current PV1/PV2(A) | `SolarCurrent_ampers{Current="PV1/PV2"}` |
| DC Power PV1/PV2(W) | `SolarPower{Power="PV1/PV2"}` |
| PV Total Power(W) | `SolarPower{Power="Total"}` |
| Total AC Output Power(W) | `OutputPower_watts{Power="Active"}` |
| Total AC Apparent Power(VA) | `OutputPower_watts{Power="Apparent"}` |
| AC Output Frequency R(Hz) | `OutputFreq{Grid="Frequency"}` |
| AC Voltage R/U/A(V) | `OutputVoltage_volts{Voltage="L1"}` |
| AC Current R/U/A(A) | `OutputCurrent_ampers{Current="L1"}` |
| Power factor | `OutputPowerFactor{PowerFactor="R"}` |
| PCC AC Current R(A) | `PCCCurrent_ampers{Current="R"}` |
| Total Grid Power(W) | `PCCPower_watts{Power="ActiveTotal"}` |
| Total Consumption Power(W) | `LoadPower_watts{Power="SystemTotal"}` |
| Cumulative Production (Active)(kWh) | `SolarProduction_watts_total{Production="Total"}` |
| Daily Production (Active)(kWh) | `SolarProduction_watts_total{Production="Today"}` |
| Generation Time Today(Min) | `SolarTime{GenerationTime="Today"}` |
| Generation Time Total(Min) | `SolarTime{GenerationTime="Total"}` |
| Total Running Hour(h) | `SolarTime{RunningTime="Total"}` (convertido para min) |
| Single Plate Ambient Temperature(℃) | `InverterTemp_celsius{Temp="Ambient"}` |
| Radiator Temperature 1(℃) | `InverterTemp_celsius{Temp="Inner"}` |
| Bus Voltage(V) | `InverterVoltage_volts{Voltage="Bus"}` |
| Insulation Impedance 1(KΩ) | `InverterInsulation{Resistance="Total"}` |
| Leak Current(mA) | `InverterLeakCurrent_mA{Current="Leak"}` |

## Passo 2: Importar no Prometheus

### Opção A: Via Remote Write API (recomendado para Prometheus 2.55+)

Requer que o Prometheus tenha a flag `--web.enable-remote-write-receiver` habilitada e suporte a out-of-order writes para dados históricos.

```bash
python3 import_to_prometheus.py --url http://<PROMETHEUS_IP>:9090
```

Para aceitar dados antigos, adicionar no `prometheus.yml`:

```yaml
storage:
  tsdb:
    out_of_order_time_window: 8760h
```

Ou verificar a flag disponível na sua versão:
```bash
prometheus --help 2>&1 | grep out-of-order
```

### Opção B: Via promtool (alternativa mais simples)

Não requer flags especiais. Funciona offline.

```bash
# Baixar promtool (vem com o Prometheus)
wget https://github.com/prometheus/prometheus/releases/download/v2.55.0/prometheus-2.55.0.linux-amd64.tar.gz
tar xzf prometheus-2.55.0.linux-amd64.tar.gz

# Criar blocos TSDB
./prometheus-2.55.0.linux-amd64/promtool tsdb create-blocks-from openmetrics openmetrics_output.txt ./blocks/

# Copiar para o volume de dados do Prometheus
docker cp ./blocks/. prometheus:/prometheus/

# Reiniciar para reconhecer os novos blocos
docker restart prometheus
```

## Observações

- Timezone dos timestamps: `America/Sao_Paulo`
- Apenas arquivos `2*.csv` são processados (ignora Daily Statistics e Detailed Data)
- Valores não numéricos ou linhas sem timestamp são ignorados
- Os nomes das métricas são idênticos aos do `InverterData.py` — o dashboard Grafana funciona sem alterações
