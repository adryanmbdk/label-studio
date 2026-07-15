/// <reference types="cypress" />

declare global {
  namespace Cypress {
    interface Chainable {
      signup(email: string, password: string): Chainable<void>;
      login(email: string, password: string): Chainable<void>;
    }
  }
}

/**
 * Cria uma nova conta via formulário de cadastro.
 * O campo `elaborate` é um honeypot anti-bot e deve permanecer vazio.
 */
Cypress.Commands.add('signup', (email: string, password: string) => {
  cy.visit('/user/signup/');
  cy.get('#email').type(email);
  cy.get('#password').type(password);
  cy.get('#signup-form button[type="submit"]').click();
});

/** Autentica um usuário existente via formulário de login. */
Cypress.Commands.add('login', (email: string, password: string) => {
  cy.visit('/user/login/');
  cy.get('#email').type(email);
  cy.get('#password').type(password);
  cy.get('#login-form button[type="submit"]').click();
});

export {};