/**
 * Testes de aceitação — fluxo de autenticação do Label Studio.
 * Cenários em Gherkin: documentacao/testes_devops.md
 *
 * Os testes são autocontidos: cada execução gera um e-mail único e cria o
 * próprio estado, sem depender de dados pré-existentes no banco.
 */

const PASSWORD = 'LabelStudio123!';

const uniqueEmail = () => `e2e-${Date.now()}-${Math.floor(Math.random() * 10000)}@example.com`;

describe('Autenticação', () => {
  beforeEach(() => {
    cy.clearCookies();
  });

  it('Cenário 1: um novo usuário consegue criar uma conta', () => {
    cy.signup(uniqueEmail(), PASSWORD);
    cy.url().should('not.include', '/user/signup');
  });

  it('Cenário 2: login com credenciais inválidas é rejeitado', () => {
    cy.login(uniqueEmail(), 'SenhaCompletamenteErrada123!');
    cy.url().should('include', '/user/login');
  });

  it('Cenário 3: um usuário registrado consegue autenticar-se', () => {
    const email = uniqueEmail();
    cy.signup(email, PASSWORD);
    cy.clearCookies();
    cy.login(email, PASSWORD);
    cy.url().should('not.include', '/user/login');
  });
});