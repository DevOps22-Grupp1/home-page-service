describe('Login Page Navigation Tests', () => {
  beforeEach(() => {
    // Visit the base URL before each test
    cy.visit('/');
  });

  it('should navigate to Login page when clicking on the Login link in the header', () => {
    // Click on the "Login" link in the header using contains
    cy.contains('a', 'Login').click();

    // Verify that the URL includes '/login'
    cy.url().should('include', '/login');
  });

});
