describe('Authentication - Registration Flow', () => {
  beforeEach(() => {
    cy.visitWithBannersDismissed('/#/register');
  });

  it('SC-AUTH-01: Successfully register a new disposable user via UI', { tags: ['@smoke'] }, () => {
    const timestamp = Date.now();
    const dynamicEmail = `cypress-ui-${timestamp}@juice-sh.op`;
    const password = 'JuicePassword123!';

    cy.intercept('POST', '**/api/Users/**').as('registerRequest');

    cy.get('#emailControl').type(dynamicEmail);
    cy.get('#passwordControl').type(password);
    cy.get('#repeatPasswordControl').type(password);

    // Open security question dropdown
    cy.get('mat-select[name="securityQuestion"]').click();
    cy.get('mat-option').first().click();

    cy.get('#securityAnswerControl').type('CypressFavoriteColor');

    cy.get('#registerButton').should('be.enabled').click();

    cy.wait('@registerRequest').its('response.statusCode').should('eq', 201);
    cy.url().should('include', '/#/login');
    cy.get('snack-bar-container', { timeout: 10000 }).should(
      'contain.text',
      'Registration completed successfully',
    );
  });

  it('SC-AUTH-02: Prevent registration when passwords mismatch', { tags: ['@regression'] }, () => {
    cy.get('#emailControl').type('mismatch-test@juice-sh.op');
    cy.get('#passwordControl').type('StrongPass123!');
    cy.get('#repeatPasswordControl').type('DifferentPass999!');

    cy.get('mat-select[name="securityQuestion"]').click();
    cy.get('mat-option').first().click();
    cy.get('#securityAnswerControl').type('SomeAnswer');

    cy.get('#registerButton').should('be.disabled');
    cy.get('.mat-error').should('contain.text', 'Passwords do not match');
  });
});
