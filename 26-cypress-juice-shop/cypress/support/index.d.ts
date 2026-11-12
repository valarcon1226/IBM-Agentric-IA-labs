/// <reference types="cypress" />
/// <reference types="@cypress/grep" />

export interface AuthedUser {
  token: string;
  bid: number;
  umail: string;
}

export interface RegisteredUser {
  id: number;
  email: string;
  role: string;
}

export interface BasketItemResponse {
  status: string;
  data: {
    id: number;
    ProductId: number;
    BasketId: number;
    quantity: number;
  };
}

declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Authenticates a user directly via API and caches session via cy.session().
       * Injects JWT token and user info into localStorage.
       */
      loginByApi(email?: string, password?: string): Chainable<null>;

      /**
       * Creates a new user via POST /api/Users.
       */
      registerByApi(
        email: string,
        password?: string,
        securityAnswer?: string,
      ): Chainable<RegisteredUser>;

      /**
       * Dismisses the Juice Shop welcome dialog and cookie consent banner.
       */
      dismissInitialBanners(): Chainable<void>;

      /**
       * Visits a URL with localStorage preconfigured to dismiss initial banners.
       */
      visitWithBannersDismissed(url: string): Chainable<void>;

      /**
       * Adds an item to basket via API.
       */
      addToBasketByApi(
        productId: number,
        quantity?: number,
        token?: string,
      ): Chainable<BasketItemResponse>;
    }
  }
}
