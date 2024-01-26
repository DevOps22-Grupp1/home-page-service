describe('About Page Navigation Tests', () => {
  beforeEach(() => {
    // Visit the base URL before each test
    cy.visit('/');
  });

  it('should navigate to About page when clicking on the About link in the header', () => {
    // Click on the "About" link in the header
    cy.contains('a', 'About').click();

    // Verify that the URL includes '/about'
    cy.url().should('include', '/about');

    // Optionally, you can add assertions to verify the content on the About page
    // For example, checking if a about is present on the About page
    cy.get('h1').should('contain', 'About');
  });

  
});
