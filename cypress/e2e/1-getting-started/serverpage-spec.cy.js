describe('Server Page Navigation Tests', () => {
  beforeEach(() => {
    // Visit the base URL before each test
    cy.visit('/');
  });

  it('should navigate to Server page when clicking on the Server link in the header', () => {
    // Click on the "Server" link in the header
    cy.contains('a', 'Server').click();

    // Verify that the URL includes '/server'
    cy.url().should('include', '/server');

    // Optionally, you can add assertions to verify the content on the About page
    // For example, checking if a python flask is present on the About page
    cy.get('h1').should('contain', 'Monitoring Server Status');
  });

});
