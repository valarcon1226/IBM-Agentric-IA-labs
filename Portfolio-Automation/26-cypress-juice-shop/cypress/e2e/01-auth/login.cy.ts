describe('Authentication - Login Flow', () => {
  it('SC-AUTH-03: Successfully login via UI with valid credentials', { tags: ['@smoke'] }, () => {
    const timestamp = Date.now();
    const email = `login-ui-${timestamp}@juice-sh.op`;
    const password = 'ValidUserPass123!';

    // Seed disposable user via API first
    cy.registerByApi(email, password);

    cy.visitWithBannersDismissed('/#/login');
    cy.intercept('POST', '**/rest/user/login').as('loginReq');

    cy.get('#email').type(email);
    cy.get('#password').type(password);
    cy.get('#loginButton').should('be.enabled').click();

    cy.wait('@loginReq').its('response.statusCode').should('eq', 200);
    cy.url().should('not.include', '/#/login');

    // Confirm session is active
    cy.window().then((win) => {
      expect(win.localStorage.getItem('token')).to.be.a('string');
    });
  });

  it(
    'SC-AUTH-04: Reject login with invalid credentials and show error',
    { tags: ['@regression'] },
    () => {
      cy.visitWithBannersDismissed('/#/login');
      cy.intercept('POST', '**/rest/user/login').as('invalidLoginReq');

      cy.get('#email').type('nonexistent-user@juice-sh.op');
      cy.get('#password').type('WrongPassword123!');
      cy.get('#loginButton').click();

      cy.wait('@invalidLoginReq').its('response.statusCode').should('eq', 401);
      cy.get('.error', { timeout: 10000 }).should('contain.text', 'Invalid email or password');
    },
  );

  it('SC-AUTH-05: Fast login via API using cy.session caching', { tags: ['@regression'] }, () => {
    cy.loginByApi('admin@juice-sh.op', 'admin123');
    cy.visitWithBannersDismissed('/#/search');

    cy.window().then((win) => {
      const token = win.localStorage.getItem('token');
      expect(token).to.be.a('string');
    });
  });
});
