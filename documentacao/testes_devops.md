# Testes de Aceitação Automatizados

Ferramenta: **Cypress 14.5.0** (já presente no monorepo, via Nx)
Local das specs: `web/apps/labelstudio-e2e/src/e2e/`
Comandos reutilizáveis: `web/apps/labelstudio-e2e/src/support/commands.ts`

## Contexto

O projeto `labelstudio-e2e` já existia configurado no monorepo, porém **sem nenhum
teste implementado** — o arquivo `src/e2e/app.cy.ts` continha apenas uma linha em
branco e `src/support/commands.ts` estava vazio. Os testes descritos abaixo são,
portanto, os primeiros testes de aceitação do módulo.

## Decisão de projeto: testes autocontidos

Cada execução gera um e-mail único (`e2e-<timestamp>-<random>@example.com`) e cria
o próprio estado através da interface. Nenhum teste depende de usuários ou projetos
pré-existentes no banco. Isso garante que a suíte:

- roda do zero em qualquer máquina, inclusive em CI;
- é idempotente — pode ser executada repetidas vezes sem limpeza manual;
- não quebra por dados locais divergentes.

Observação técnica: o formulário de cadastro possui o campo `elaborate`, sem rótulo
visível — trata-se de um *honeypot* anti-bot. O comando `cy.signup()` deliberadamente
não o preenche, pois um valor nesse campo faz o servidor rejeitar o cadastro.

## Cenários

### Cenário 1 — Cadastro de novo usuário

```gherkin
Funcionalidade: Autenticação
  Cenário: Um novo usuário consegue criar uma conta
    Dado que o visitante está na página de cadastro
    Quando ele informa um e-mail ainda não registrado e uma senha válida
    E confirma a criação da conta
    Então ele deve ser redirecionado para fora da página de cadastro
```

**O que cobre:** o fluxo de entrada do sistema. É pré-requisito de qualquer outro
uso da aplicação, e valida o `POST /user/signup/` de ponta a ponta — template,
CSRF, validação, criação do usuário e redirecionamento.

### Cenário 2 — Rejeição de credenciais inválidas

```gherkin
Funcionalidade: Autenticação
  Cenário: Login com credenciais inválidas é rejeitado
    Dado que o visitante está na página de login
    Quando ele informa um e-mail inexistente e uma senha incorreta
    E tenta autenticar-se
    Então uma mensagem de erro deve ser exibida
    E ele deve permanecer na página de login
```

**O que cobre:** o caminho negativo — garante que o sistema não autentica quem não
deve. A asserção verifica a presença visível do elemento `p.error` (renderizado pelo
bloco `form.non_field_errors` do template), e não apenas a URL: verificar somente a
URL faria o teste passar mesmo que o formulário não fosse submetido, pois a página
de login é a própria origem da navegação.

### Cenário 3 — Autenticação de usuário registrado

```gherkin
Funcionalidade: Autenticação
  Cenário: Um usuário registrado consegue autenticar-se
    Dado que existe uma conta recém-criada com credenciais conhecidas
    E que a sessão anterior foi encerrada
    Quando o usuário informa suas credenciais corretas na página de login
    Então ele deve ser redirecionado para fora da página de login
```

**O que cobre:** o fluxo crítico do produto. Encadeia cadastro → limpeza de sessão →
login, exercitando o ciclo completo de autenticação com credenciais reais criadas
pelo próprio teste.

## Instruções de execução

**Pré-requisito:** o Label Studio precisa estar em execução em `http://localhost:8080`
(valor de `baseUrl` definido em `web/apps/labelstudio-e2e/project.json`). O alvo `e2e`
não sobe o servidor automaticamente.

Terminal 1 — subir a aplicação:

    DJANGO_DB=sqlite poetry run python label_studio/manage.py runserver 8080

Terminal 2 — executar os testes (headless):

    cd web
    npx nx run labelstudio-e2e:e2e

Modo interativo (requer servidor gráfico; no WSL exige WSLg ou X server):

    cd web
    npx nx run labelstudio-e2e:e2e --watch

Em ambientes Linux/WSL, o Cypress pode exigir bibliotecas de sistema adicionais:

    sudo apt-get install -y libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev \
      libnss3 libxss1 libasound2 libxtst6 xauth xvfb

## Resultado

    Tests:    3
    Passing:  3
    Failing:  0
    Duration: ~16s

---

# DevOps e CI/CD

## Análise do pipeline existente

O Label Studio possui um pipeline maduro no GitHub Actions, com mais de 40 workflows.
Os principais:

| Workflow | Função |
|---|---|
| `tests.yml` | pytest em 4 versões de Python (3.10–3.13), SQLite + PostgreSQL + Windows |
| `ruff.yml` | análise estática de Python |
| `bandit.yml` | análise de segurança (Python) |
| `codeql.yml` | análise de segurança (multi-linguagem) |
| `gitleaks.yml` | detecção de segredos vazados |
| `biome.yml` | lint e formatação de JS/TS |
| `tests-yarn-lsf.yml` | testes Cypress do `libs/editor` |
| `tests-yarn-unit.yml` | testes unitários do frontend |
| `validator-pull-request-labeler.yml` | valida o título dos PRs (Conventional Commits) |

**CD:** o projeto publica no PyPI (`build_pypi.yml`, `build_pypi_nightly.yml`),
constrói e promove imagens Docker (`docker-build.yml`, `docker-release-promote.yml`)
e atualiza o Helm chart (`bump-helm-chart.yml`). Esses fluxos dependem de
credenciais de publicação do mantenedor (secrets indisponíveis em um fork),
portanto não são endereçáveis neste trabalho.

**Cobertura de código:** já existe via Codecov no `tests.yml`
(`--cov=. --cov-report=xml`), porém o passo é condicionado a
`github.event.pull_request.head.repo.fork == false` e depende de
`secrets.CODECOV_TOKEN` — ou seja, é deliberadamente ignorado em forks.

**Observação sobre checks vermelhos:** os validadores `Poetry Lock Change Size` e
`PyProject Package Version` falham em todos os PRs deste fork porque utilizam
`secrets.GIT_PAT`, um token do mantenedor. O GitHub não expõe secrets do
repositório original em forks, por design de segurança — trata-se de uma
limitação de ambiente, não de defeito nas contribuições.

## Melhorias avaliadas e descartadas

A análise do pipeline levou ao descarte de três propostas iniciais, por
redundância — registradas aqui porque a justificativa do descarte faz parte
da análise:

1. **Adicionar pylint ao CI** — descartado: `ruff.yml` já executa análise
   estática de Python, e o Ruff cobre o mesmo escopo com melhor desempenho.
2. **Criar workflow para os testes de `label_studio/tests/ml/`** — descartado:
   o `tests.yml` executa a suíte pytest inteira, sem filtro de path, portanto
   os testes criados no Caminho B já são cobertos.
3. **Adicionar cache de dependências** — descartado: `tests.yml` já usa
   `cache: 'poetry'` e `tests-yarn-lsf.yml` já mantém cache do binário do Cypress.

## Lacuna identificada

Uma busca por `labelstudio-e2e` em todos os workflows retorna **zero ocorrências**:

    grep -rn "labelstudio-e2e\|ls:e2e\|test:e2e\|cypress" .github/workflows/

O Cypress presente no `tests-yarn-lsf.yml` pertence ao `libs/editor` — um
aplicativo distinto dentro do monorepo.

Conclusão: o projeto `labelstudio-e2e` estava configurado no monorepo, **sem
nenhum teste implementado** e **sem execução no CI**. A primeira lacuna foi
tratada com os testes descritos na primeira parte deste documento; a segunda é
tratada pela melhoria abaixo.

## Melhoria implementada

Novo workflow: `.github/workflows/e2e-labelstudio.yml`

Disparado em `pull_request` para `develop`, o job:

1. instala as dependências Python (Poetry) e Node (Yarn), com cache — seguindo o
   padrão já adotado pelos demais workflows do projeto;
2. instala as dependências de sistema exigidas pelo Label Studio;
3. gera o arquivo de versão e executa as migrações (SQLite);
4. sobe o servidor em `localhost:8080` em background e aguarda a resposta via `wait-on`;
5. executa `nx run labelstudio-e2e:e2e`;
6. em caso de falha, publica screenshots e vídeos do Cypress como artefato do job.

**Decisão de escopo:** os cenários exercitam apenas `/user/signup/` e `/user/login/`,
servidos por templates Django — não exigem o build do frontend React. Isso mantém o
job significativamente mais enxuto do que seria um e2e da interface completa.

**Resultado:** o check `E2E — labelstudio-e2e (Cypress)` executa e passa nos Pull
Requests abertos contra `develop`.
