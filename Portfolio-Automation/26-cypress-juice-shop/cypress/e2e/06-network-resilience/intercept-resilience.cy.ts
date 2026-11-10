describe('Network Resilience - cy.intercept Simulation', () => {
  it(
    'SC-NET-01: Simulate backend 500 error on product search and handle gracefully',
    { tags: ['@regression'] },
    () => {
      cy.intercept('GET', '**/rest/products/search*', {
        statusCode: 500,
        body: {
          status: 'error',
          message: 'Simulated 500 Internal Server Error for resilience verification',
        },
      }).as('mock500Search');

      cy.visitWithBannersDismissed('/#/search');
      cy.wait('@mock500Search').its('response.statusCode').should('eq', 500);

      // Verify UI handles error without crashing (empty state or snackbar rendered)
      cy.get('app-search-result').should('be.visible');
      cy.get('mat-card:not(.emptyState)').should('have.length', 0);
    },
  );

  it(
    'SC-NET-02: Simulate slow network latency on product search and verify resolution',
    { tags: ['@regression'] },
    () => {
      cy.intercept('GET', '**/rest/products/search*', (req) => {
        req.continue((res) => {
          res.delay = 1000;
        });
      }).as('delayedSearch');

      cy.visitWithBannersDismissed('/#/search');
      cy.wait('@delayedSearch').its('response.statusCode').should('eq', 200);

      // Verify catalog resolves and renders products after simulated latency
      cy.get('mat-card:not(.emptyState)', { timeout: 10000 }).should('have.length.at.least', 1);
    },
  );

  it(
    'SC-NET-03: Simulate backend 500 on feedback submission and verify error notification',
    { tags: ['@regression'] },
    () => {
      cy.intercept('GET', '**/rest/captcha/**').as('getCaptcha');
      cy.intercept('POST', '**/api/Feedbacks/**', {
        statusCode: 500,
        body: { error: 'Database connection failed' },
      }).as('mock500Feedback');

      cy.visitWithBannersDismissed('/#/contact');

      cy.wait('@getCaptcha').then((interception) => {
        const captchaAnswer = interception.response?.body.answer;

        cy.get('textarea').filter(':visible').type('Testing resilience against server failures');
        cy.get('mat-slider').click();
        cy.get('input').filter(':visible').last().type(String(captchaAnswer));

        cy.get('#submitButton').should('be.enabled').click();

        cy.wait('@mock500Feedback').its('response.statusCode').should('eq', 500);

        // Verify error snackbar or notification is shown
        cy.get('snack-bar-container', { timeout: 10000 }).should('be.visible');
      });
    },
  );
});
