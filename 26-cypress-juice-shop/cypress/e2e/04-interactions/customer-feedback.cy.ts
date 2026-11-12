describe('User Interactions - Customer Feedback', () => {
  it(
    'SC-FDBK-01: Successfully submit feedback with comment, rating, and captcha',
    { tags: ['@regression'] },
    () => {
      cy.intercept('GET', '**/rest/captcha/**').as('getCaptcha');
      cy.intercept('POST', '**/api/Feedbacks/**').as('submitFeedback');

      cy.visitWithBannersDismissed('/#/contact');

      cy.wait('@getCaptcha').then((interception) => {
        const captchaAnswer = interception.response?.body.answer;

        cy.get('textarea')
          .filter(':visible')
          .type('Fantastic organic juices and lightning-fast delivery experience!');

        // Select rating on slider
        cy.get('mat-slider').click();

        // Enter solved captcha answer
        cy.get('input').filter(':visible').last().type(String(captchaAnswer));

        cy.get('#submitButton').should('be.enabled').click();

        cy.wait('@submitFeedback').its('response.statusCode').should('eq', 201);
        cy.get('snack-bar-container', { timeout: 10000 }).should(
          'contain.text',
          'Thank you for your feedback',
        );
      });
    },
  );

  it(
    'SC-FDBK-02: Prevent feedback submission when fields are empty',
    { tags: ['@regression'] },
    () => {
      cy.visitWithBannersDismissed('/#/contact');

      // Both comment and captcha are empty initially
      cy.get('#submitButton').should('be.disabled');

      // Type comment only
      cy.get('textarea').filter(':visible').type('Incomplete feedback');
      cy.get('#submitButton').should('be.disabled');
    },
  );
});
