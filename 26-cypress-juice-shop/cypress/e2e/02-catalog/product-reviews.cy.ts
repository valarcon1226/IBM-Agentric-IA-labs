describe('Catalog - Product Reviews', () => {
  beforeEach(() => {
    cy.visitWithBannersDismissed('/#/search');
  });

  it('SC-CAT-03: View product reviews dialog for an item', { tags: ['@regression'] }, () => {
    cy.intercept('GET', /\/rest\/products\/\d+\/reviews/).as('getReviews');

    // Click on the first product card to open details modal
    cy.get('mat-card:not(.emptyState)').first().click();

    cy.wait('@getReviews').its('response.statusCode').should('eq', 200);

    // Verify modal is open and displays product details
    cy.get('mat-dialog-container').should('be.visible');
    cy.get('mat-dialog-container h1').should('be.visible');

    // Expand reviews panel if present
    cy.get('mat-expansion-panel-header').contains('Reviews').click();
    cy.get('mat-expansion-panel-header').should('have.attr', 'aria-expanded', 'true');

    // Close the dialog
    cy.get('button[aria-label="Close Dialog"]').click();
    cy.get('mat-dialog-container').should('not.exist');
  });

  it('SC-CAT-04: Submit a product review as authenticated user', { tags: ['@regression'] }, () => {
    cy.loginByApi('admin@juice-sh.op', 'admin123');
    cy.visitWithBannersDismissed('/#/search');

    cy.intercept('PUT', /\/rest\/products\/\d+\/reviews/).as('submitReview');
    cy.intercept('GET', /\/rest\/products\/\d+\/reviews/).as('refreshReviews');

    cy.get('mat-card:not(.emptyState)').first().click();
    cy.wait('@refreshReviews');

    const timestamp = Date.now();
    const reviewMessage = `Great item ${timestamp}`;

    cy.get('textarea[aria-label="Text field to review a product"]').should('be.visible');
    cy.get('textarea[aria-label="Text field to review a product"]').clear();
    cy.get('textarea[aria-label="Text field to review a product"]').type(reviewMessage);

    cy.get('#submitButton').should('be.enabled').click();

    cy.wait('@submitReview').its('response.statusCode').should('eq', 201);

    // Close dialog
    cy.get('button[aria-label="Close Dialog"]').click();
  });
});
