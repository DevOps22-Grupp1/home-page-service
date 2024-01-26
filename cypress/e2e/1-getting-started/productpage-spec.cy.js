describe('Navigation Tests', () => {
  it('should navigate to Products page', () => {
    // Visit the base URL
    cy.visit('/');

    // Clicking on the element using cy.contains
    cy.contains('a', 'Products').click();

    // Log information about the element using cy.get and cy.log
    cy.get('a').contains('Products').then(($el) => {
      cy.log(`Found ${$el.length} element(s) matching the selector.`);
    });

    // Verifing the URL includes '/products'
    cy.url().should('include', '/products');
  });
});


