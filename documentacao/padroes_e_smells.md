# Padrões de Projeto — Caminho B

Arquivo alvo da refatoração: `label_studio/ml/api_connector.py`

## Padrões de Projeto

### 1. Builder — `MLRequestPayloadBuilder`
**Onde será aplicado:** `label_studio/ml/api_connector.py`
**Justificativa:** os métodos `train`, `_prep_prediction_req` e `setup` da classe
`MLApi` montam manualmente dicionários de requisição, repetindo chaves como
`project`, `label_config`, `hostname` e `params`. O padrão Builder permite montar
esse payload de forma incremental e reaproveitável, através de métodos encadeados
(`with_project`, `with_hostname`, `with_label_config`, `with_params`), eliminando
a duplicação.

### 2. Facade — `MLApi`
**Onde já está aplicado:** `label_studio/ml/api_connector.py`
**Justificativa:** a classe `MLApi` já expõe uma interface simples
(`train()`, `make_predictions()`, `health()`, `setup()`, `delete()`) escondendo
a complexidade de sessões HTTP, retries e timeouts (`BaseHTTPAPI`). Na
refatoração, esse papel de Facade é reforçado e documentado, e passa a
esconder também a montagem de payload feita pelo Builder.