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
