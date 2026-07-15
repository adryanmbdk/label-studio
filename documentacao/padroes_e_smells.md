# Padrões de Projeto e Code Smells — Caminho B

Arquivo refatorado: `label_studio/ml/api_connector.py`
Módulo responsável pela integração HTTP entre o backend Django do Label Studio
e servidores de Machine Learning externos.

## Code Smells

### 1. Duplicated Code — resolução de hostname repetida
**Trecho original** (repetido identicamente em `train`, `_prep_prediction_req` e `setup`):
```python
'hostname': settings.HOSTNAME if settings.HOSTNAME else ('http://localhost:' + settings.INTERNAL_PORT),
```
**Problema:** a mesma regra de negócio em 3 lugares. Alterá-la exige lembrar de
editar todas as ocorrências — caso clássico de Shotgun Surgery, com risco de
divergência silenciosa entre os payloads.
**Solução aplicada:** extraída para a função `get_ml_backend_hostname()`,
tornando-se fonte única de verdade. As 3 ocorrências passaram a chamá-la.

### 2. Duplicated Code / violação do OCP — payloads montados manualmentehead -5 documentacao/padroes_e_smells.md
**Trecho original** (`train`, `_prep_prediction_req` e `setup` montavam dicts próprios):
```python
request = {
    'annotations': tasks_ser,
    'project': self._create_project_uid(project),
    'label_config': project.label_config,
    'hostname': settings.HOSTNAME if settings.HOSTNAME else (...),
    'params': {'login': project.task_data_login, 'password': project.task_data_password},
}
```
**Problema:** as chaves `project`, `label_config`, `hostname` e `params` se repetem
entre métodos. Adicionar um campo novo ao protocolo do ML backend exigiria editar
vários métodos manualmente, com risco de esquecer algum (violação do
Open/Closed Principle).
**Solução aplicada:** padrão Builder (`MLRequestPayloadBuilder`), que monta o
payload por composição de métodos encadeados.

### 3. Violação do SRP em `BaseHTTPAPI._prepare_kwargs`
**Trecho original:**
```python
def _prepare_kwargs(self, kwargs):
    if 'timeout' not in kwargs:
        kwargs['timeout'] = self._connection_timeout, self._timeout
    if self._basic_auth[0] and self._basic_auth[1]:
        kwargs['auth'] = HTTPBasicAuth(*self._basic_auth)
    elif isinstance(kwargs['timeout'], float) or isinstance(kwargs['timeout'], int):
        kwargs['timeout'] = (self._connection_timeout, kwargs['timeout'])
```
**Problema:** o método acumula duas responsabilidades (timeout e autenticação)
em um único bloco condicional. Pior: o `elif` faz o ajuste do timeout depender de
**não** haver autenticação básica configurada — um acoplamento sem justificativa
funcional, provável bug latente. O pylint sinalizava o trecho com `R1701`
(consider-merging-isinstance) e o radon classificava o método como complexidade **B**.
**Solução aplicada:** separado em `_apply_timeout()` e `_apply_auth()`, cada um
com responsabilidade única, orquestrados por `_prepare_kwargs()`. O acoplamento
acidental entre timeout e auth foi eliminado.

### Bônus — erro real eliminado durante a refatoração
Durante o processo, a análise estática acusou `E0602: Undefined variable 'request'`
e `W0101: Unreachable code`, resultantes de código morto no `_prep_prediction_req`.
Ambos foram removidos. A monitoração contínua com pylint durante a refatoração
(e não apenas antes/depois) permitiu identificá-los.

## Padrões de Projeto

### 1. Builder — `MLRequestPayloadBuilder`
**Onde foi aplicado:** `label_studio/ml/api_connector.py` (classe nova, criada nesta refatoração).
**Justificativa:** resolve o Smell 2. Permite montar os payloads enviados ao ML
backend de forma incremental e reaproveitável, via métodos encadeados
(`with_project`, `with_label_config`, `with_hostname`, `with_params`, `with_extra`),
eliminando a duplicação de chaves entre `train`, `_prep_prediction_req` e `setup`.
Novos campos do protocolo passam a ser adicionados em um único lugar.

### 2. Facade — `MLApi`
**Onde foi identificado:** `label_studio/ml/api_connector.py` (padrão pré-existente no projeto).
**Justificativa:** `MLApi` já implementava o padrão Facade, expondo uma interface
simples (`train()`, `make_predictions()`, `health()`, `setup()`, `delete()`) que
esconde a complexidade de sessões HTTP, retries e timeouts herdada de `BaseHTTPAPI`.
Esta refatoração **identificou, documentou e reforçou** esse papel: o Facade passou
a esconder também a montagem de payload, agora delegada ao Builder — tornando-se
mais fino e mais coeso.

## Métricas — antes e depois

| Métrica | Antes | Depois | Variação |
|---|---|---|---|
| Pylint (nota geral) | 6.47/10 | 7.14/10 | **+0.67** |
| Radon — complexidade ciclomática média | A (2.03) | A (1.68) | **−17%** |
| Blocos com complexidade B | 2 (`_request`, `_prepare_kwargs`) | 1 (`_request`) | **−1** |
| Erros de análise estática (E0602/W0101) | — | 0 | eliminados |

Observação metodológica: os avisos `E0401 (import-error)` e as opções obsoletas do
`.pylintrc` aparecem em ambas as execuções (o pylint roda fora do ambiente Poetry
configurado do projeto). São constantes nos dois relatórios e, portanto, não
interferem na comparação relativa.

Relatórios completos em `documentacao/evidencias/`.

## Evidências de teste

- **Regressão:** os 8 testes existentes em `label_studio/tests/ml/` passam antes e
  depois da refatoração — comportamento externo preservado, nenhum payload mudou de formato.
- **Novos testes unitários:** 5 testes criados em
  `label_studio/tests/ml/test_api_connector_refactor.py`, cobrindo a resolução de
  hostname (com e sem `settings.HOSTNAME`), a montagem incremental do Builder, o
  isolamento de estado entre instâncias do Builder e a extração de `create_project_uid`.
- **Total:** 13 testes passando no módulo `ml`.

Execução:
```bash
DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio poetry run pytest -vv label_studio/tests/ml/
```