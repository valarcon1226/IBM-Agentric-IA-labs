describe('User Interactions - Language Switch', () => {
  it(
    'SC-LANG-01: Change UI language to German and verify localized text',
    { tags: ['@regression'] },
    () => {
      cy.intercept('GET', '**/assets/i18n/de_DE.json').as('loadGermanI18n');

      cy.visitWithBannersDismissed('/#/search');

      // Open language menu from top navbar
      cy.get('button[aria-label="Language selection menu"]').click();

      // Select German option
      cy.get('mat-radio-button, .mat-menu-item').contains('Deutsch').click();

      cy.wait('@loadGermanI18n').its('response.statusCode').should('eq', 200);

      // Verify UI reflects German localized labels (e.g. Account becomes Konto)
      cy.get('#navbarAccount').should('contain.text', 'Konto');
    },
  );
});
