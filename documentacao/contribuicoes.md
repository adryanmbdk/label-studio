# Contribuições

## Identificação

| | |
|---|---|
| **Disciplina** | CSI410 — Engenharia de Software II (2026/1) |
| **Projeto open source** | [Label Studio](https://github.com/HumanSignal/label-studio) |
| **Fork** | https://github.com/adryanmbdk/label-studio |
| **Integrantes** | Mateus Serretti Mendes Peixoto · Adryan Martins Batista dos Santos |

---

## Caminho A — Manutenção Evolutiva/Corretiva

**Issue escolhida:** [HumanSignal/label-studio#9715](https://github.com/HumanSignal/label-studio/issues/9715)
— *RuntimeWarning: Accessing the database during app initialization on Docker startup (Django 5.1)*

**Pull Request:** [#5](https://github.com/adryanmbdk/label-studio/pull/5)

### Descrição da solução

Em `label_studio/labels_manager/serializers.py`, dois campos `PrimaryKeyRelatedField`
eram declarados com `queryset=Project.objects.all()` no corpo da classe. Atributos de
classe são avaliados no momento do import — que ocorre durante `AppConfig.ready()` —
disparando o `RuntimeWarning` do Django 5.1 sobre acesso ao banco durante a
inicialização da aplicação.

A correção substitui o QuerySet pelo Manager em ambas as ocorrências:

    # Antes
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    # Depois
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects)

O DRF aceita tanto QuerySet quanto Manager em `PrimaryKeyRelatedField`; ao receber um
Manager, resolve o queryset via `get_queryset()` apenas no momento da validação da
requisição, eliminando o acesso ao banco durante a inicialização.

**Validação:** servidor iniciado com `python -W error::RuntimeWarning manage.py runserver`
— nenhum `RuntimeWarning` emitido após a correção.

---

## Caminho B — Engenharia de Qualidade e Refatoração

**Pull Requests:** [#1](https://github.com/adryanmbdk/label-studio/pull/1) (padrões) ·
[#2](https://github.com/adryanmbdk/label-studio/pull/2) (refatoração)

**Arquivo refatorado:** `label_studio/ml/api_connector.py` — módulo de integração HTTP
entre o backend Django e servidores de Machine Learning externos.

### Code smells corrigidos

1. **Duplicated Code** — a resolução do hostname estava repetida identicamente em
   `train`, `_prep_prediction_req` e `setup`. Extraída para `get_ml_backend_hostname()`.
2. **Duplicated Code / violação do OCP** — cada método montava seu próprio dicionário
   de payload, repetindo chaves. Resolvido com o padrão Builder.
3. **Violação do SRP** — `_prepare_kwargs` misturava timeout e autenticação em um único
   bloco condicional, com um `elif` que acoplava indevidamente as duas regras. Separado
   em `_apply_timeout()` e `_apply_auth()`.

Adicionalmente, foram eliminados `E0602 (undefined-variable)` e `W0101 (unreachable)`,
decorrentes de código morto identificado durante o processo.

### Padrões de projeto

- **Builder** (`MLRequestPayloadBuilder`) — classe nova, criada nesta refatoração.
- **Facade** (`MLApi`) — padrão pré-existente, identificado, documentado e reforçado
  (passou a delegar a montagem de payload ao Builder).

### Resultados medidos

| Métrica | Antes | Depois |
|---|---|---|
| Pylint | 6.47/10 | 7.14/10 (**+0.67**) |
| Radon — complexidade média | A (2.03) | A (1.68) (**−17%**) |
| Métodos com complexidade B | 2 | 1 |
| Testes de regressão | 8 passando | 8 passando (comportamento preservado) |
| Testes unitários novos | — | 5 |

Detalhamento em [`padroes_e_smells.md`](./padroes_e_smells.md); relatórios brutos em
[`evidencias/`](./evidencias/).

---

## Lista de todos os Pull Requests

| PR | Conteúdo | Link | Autor | Revisor |
|---|---|---|---|---|
| PR1 | Arquitetura | [#4](https://github.com/adryanmbdk/label-studio/pull/4) | Adryan | Mateus |
| PR2 | Padrões | [#1](https://github.com/adryanmbdk/label-studio/pull/1) | Mateus | — |
| PR3 | Refatoração | [#2](https://github.com/adryanmbdk/label-studio/pull/2) | Mateus | — |
| PR4 | Testes | [#3](https://github.com/adryanmbdk/label-studio/pull/3) | Mateus | Adryan |
| PR5 | DevOps | [#6](https://github.com/adryanmbdk/label-studio/pull/6) | Mateus | Adryan |
| PR6 | Issue resolvida | [#5](https://github.com/adryanmbdk/label-studio/pull/5) | Adryan | Mateus |
| PR7 | Este documento | [#7](https://github.com/adryanmbdk/label-studio/pull/7) | Mateus | Adryan |

---

## Papel de cada integrante

### Mateus Serretti Mendes Peixoto

- **Caminho B (PR2, PR3)** — análise e refatoração de `ml/api_connector.py`:
  identificação dos 3 code smells, aplicação do padrão Builder, separação de
  responsabilidades em `BaseHTTPAPI`, medição de qualidade antes/depois (pylint, radon)
  e redação de `padroes_e_smells.md`.
- **Testes (PR4)** — 5 testes unitários do módulo `ml` e 3 testes de aceitação em
  Cypress (`auth.cy.ts`), além dos comandos reutilizáveis `cy.signup()` / `cy.login()`
  e da redação de `testes_devops.md`.
- **DevOps (PR5)** — análise do pipeline existente (40+ workflows), avaliação e descarte
  de propostas redundantes, e implementação do workflow `e2e-labelstudio.yml`.
- **Revisão** — PR1 e PR6.

### Adryan Martins Batista dos Santos

- **Caminho A (PR6)** — seleção da issue no repositório original, diagnóstico da causa
  raiz, implementação da correção e validação.
- **Arquitetura (PR1)** — análise da arquitetura do Label Studio e elaboração dos
  diagramas em Mermaid (`arquitetura.md`).
- **Revisão** — PR4 e PR5.

---

## Ferramentas utilizadas

| Categoria | Ferramenta | Onde |
|---|---|---|
| Controle de versão | GitHub (fork + Pull Requests) | 7 PRs |
| Modelagem | Mermaid | `arquitetura.md` (PR1) |
| Testes de aceitação | Cypress 14.5.0 | `auth.cy.ts` (PR4) |
| Testes unitários | pytest | `test_api_connector_refactor.py` (PR3) |
| Qualidade de código | pylint · radon | `evidencias/` (PR3) |
| CI/CD | GitHub Actions | `e2e-labelstudio.yml` (PR5) |
