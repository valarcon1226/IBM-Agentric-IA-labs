describe('Cart and Checkout - Address Management', () => {
  it('SC-ADDR-01: Add a new delivery address via UI form', { tags: ['@regression'] }, () => {
    const timestamp = Date.now();
    const email = `addr-user-${timestamp}@juice-sh.op`;
    const password = 'AddrPass123!';

    cy.registerByApi(email, password);
    cy.loginByApi(email, password);

    cy.visitWithBannersDismissed('/#/address/saved');
    cy.intercept('POST', '**/api/Addresss/**').as('createAddress');

    // Click Add New Address button from saved addresses page
    cy.get('button[aria-label="Add a new address"]').click();
    cy.url().should('include', '/#/address/create');

    cy.get('input[placeholder*="country" i]').type('Colombia');
    cy.get('input[placeholder*="name" i]').type('Valentina Alarcon');
    cy.get('input[placeholder*="mobile" i]').type('3001234567');
    cy.get('input[placeholder*="ZIP" i]').type('110111');
    cy.get('textarea[placeholder*="address" i]').type(`Calle ${timestamp} Carrera 15`);
    cy.get('input[placeholder*="city" i]').type('Bogota');
    cy.get('input[placeholder*="state" i]').type('Cundinamarca');

    cy.get('#submitButton').should('be.enabled').click();

    cy.wait('@createAddress').its('response.statusCode').should('eq', 201);
    cy.url().should('include', '/#/address/saved');
    cy.get('mat-table, table, mat-card').should('contain.text', `Calle ${timestamp} Carrera 15`);
  });
});
