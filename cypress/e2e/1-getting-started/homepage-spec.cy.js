describe('Hello World Test', () => {
  it('should return a 200 status code and contain "Welcome to Scamazon!"', () => {
    cy.request('/')
      .its('status')
      .should('equal', 200);

    cy.request('/')
      .its('body')
      .should('include', 'Welcome to Scamazon!');
  });
});
