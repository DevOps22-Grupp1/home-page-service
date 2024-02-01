const stripe = Stripe("pk_test_51OexmCIffcetN3aYdG0FsFpdBDHfQ6J3kOgVGUk3co65TU8fz1rhX9fyd6pVAPkeQNmYtR7p0xD7JTL0XbDD5LHE00EdTfFaoK");

initialize();

// Create a Checkout Session as soon as the page loads
async function initialize() {
  const response = await fetch("/create-checkout-session", {
    method: "POST",
  });

  const { clientSecret } = await response.json();

  const checkout = await stripe.initEmbeddedCheckout({
    clientSecret,
  });

  // Mount Checkout
  checkout.mount('#checkout');
}