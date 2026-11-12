describe('Cart and Checkout - Full Checkout Flow', () => {
  it(
    'SC-CHK-01: Complete entire purchase flow from basket to order confirmation',
    { tags: ['@smoke'] },
    () => {
      const timestamp = Date.now();
      const email = `checkout-user-${timestamp}@juice-sh.op`;
      const password = 'CheckoutPass123!';

      cy.registerByApi(email, password);
      cy.loginByApi(email, password);

      // Seed delivery address via saved address page
      cy.visitWithBannersDismissed('/#/address/saved');
      cy.get('button[aria-label="Add a new address"]').click();
      cy.get('input[placeholder*="country" i]').type('Colombia');
      cy.get('input[placeholder*="name" i]').type('QA Lead');
      cy.get('input[placeholder*="mobile" i]').type('3109876543');
      cy.get('input[placeholder*="ZIP" i]').type('110111');
      cy.get('textarea[placeholder*="address" i]').type(`Calle ${timestamp} Carrera 7`);
      cy.get('input[placeholder*="city" i]').type('Bogota');
      cy.get('input[placeholder*="state" i]').type('Cundinamarca');
      cy.get('#submitButton').click();
      cy.url().should('include', '/#/address/saved');

      // Add item to basket
      cy.visitWithBannersDismissed('/#/search');
      cy.intercept('POST', '**/api/BasketItems/**').as('addToBasket');
      cy.get('button[aria-label="Add to Basket"]').first().click();
      cy.wait('@addToBasket');

      // Navigate to basket and start checkout
      cy.visitWithBannersDismissed('/#/basket');
      cy.get('#checkoutButton').click();

      // Step 1: Select Address
      cy.url().should('include', '/#/address/select');
      cy.get('mat-radio-button').first().click();
      cy.get('button[aria-label="Proceed to payment selection"]').should('be.enabled').click();

      // Step 2: Select Delivery Method
      cy.url().should('include', '/#/delivery-method');
      cy.get('mat-radio-button').first().click();
      cy.get('button[aria-label="Proceed to delivery method selection"]')
        .should('be.enabled')
        .click();

      // Step 3: Payment Method - Add new card using native select elements
      cy.url().should('include', '/#/payment/shop');
      cy.get('mat-expansion-panel-header').contains('Add new card').click();
      cy.get('input[type="text"]').filter(':visible').first().type('QA Lead');
      cy.get('input[type="number"]').filter(':visible').first().type('4111111111111111');
      cy.get('mat-expansion-panel select').first().select(1); // Select 1st month
      cy.get('mat-expansion-panel select').last().select(1); // Select 1st year
      cy.get('#submitButton').click();

      // Select the card radio button and proceed
      cy.get('mat-table mat-radio-button, mat-radio-button').first().click();
      cy.get('button[aria-label="Proceed to review"]').should('be.enabled').click();

      // Step 4: Order Summary and Final Checkout
      cy.url().should('include', '/#/order-summary');
      cy.intercept('POST', '**/rest/basket/*/checkout').as('checkoutRequest');
      cy.get('#checkoutButton').should('be.enabled').click();

      // Confirmation
      cy.wait('@checkoutRequest').its('response.statusCode').should('eq', 200);
      cy.url().should('include', '/#/order-completion');
      cy.get('mat-card').should('contain.text', 'Thank you for your purchase!');
    },
  );
});
