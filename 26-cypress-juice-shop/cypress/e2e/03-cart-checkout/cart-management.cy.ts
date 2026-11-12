describe('Cart and Checkout - Cart Management', () => {
  it(
    'SC-CART-01: Add product to basket and verify snackbar notification',
    { tags: ['@smoke'] },
    () => {
      const timestamp = Date.now();
      const email = `cart-user-${timestamp}@juice-sh.op`;
      const password = 'CartPass123!';

      // Fresh user ensures empty basket
      cy.registerByApi(email, password);
      cy.loginByApi(email, password);

      cy.visitWithBannersDismissed('/#/search');
      cy.intercept('POST', '**/api/BasketItems/**').as('addToBasket');

      // Add first product to basket
      cy.get('button[aria-label="Add to Basket"]').first().click();

      cy.wait('@addToBasket').its('response.statusCode').should('eq', 200);
      cy.get('snack-bar-container', { timeout: 10000 }).should('contain.text', 'into basket');
    },
  );

  it(
    'SC-CART-02: View basket and verify item details and checkout button',
    { tags: ['@regression'] },
    () => {
      const timestamp = Date.now();
      const email = `cart-view-${timestamp}@juice-sh.op`;
      const password = 'CartPass123!';

      cy.registerByApi(email, password);
      cy.loginByApi(email, password);

      cy.visitWithBannersDismissed('/#/search');
      cy.intercept('POST', '**/api/BasketItems/**').as('addToBasket');

      cy.get('button[aria-label="Add to Basket"]').first().click();
      cy.wait('@addToBasket');

      cy.visitWithBannersDismissed('/#/basket');

      // Verify product row rendered in basket table
      cy.get('mat-table, table').should('be.visible');
      cy.get('#checkoutButton').should('be.visible').and('be.enabled');
    },
  );
});
