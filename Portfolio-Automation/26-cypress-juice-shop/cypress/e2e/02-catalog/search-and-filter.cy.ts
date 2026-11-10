describe('Catalog - Search and Filter', () => {
  beforeEach(() => {
    cy.visitWithBannersDismissed('/#/search');
  });

  it('SC-CAT-01: Search for an existing product and filter results', { tags: ['@smoke'] }, () => {
    cy.get('mat-icon').contains('search').click();
    cy.get('#searchQuery input').should('be.visible');
    cy.get('#searchQuery input').clear();
    cy.get('#searchQuery input').type('apple{enter}');

    cy.url().should('include', 'q=apple');
    cy.get('mat-card').should('have.length.at.least', 1);
    cy.get('mat-card').first().should('contain.text', 'Apple');
  });

  it(
    'SC-CAT-02: Search for non-existent product shows empty results',
    { tags: ['@regression'] },
    () => {
      cy.get('mat-icon').contains('search').click();
      cy.get('#searchQuery input').should('be.visible');
      cy.get('#searchQuery input').clear();
      cy.get('#searchQuery input').type('xyznonexistent{enter}');

      cy.url().should('include', 'q=xyznonexistent');
      cy.get('mat-card:not(.emptyState)').should('have.length', 0);
      cy.get('mat-card.emptyState').should('be.visible').and('contain.text', 'No results found');
    },
  );
});
