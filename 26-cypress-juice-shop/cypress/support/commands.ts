import { RegisteredUser, BasketItemResponse } from './index';

Cypress.Commands.add('dismissInitialBanners', () => {
  cy.setCookie('welcomebanner_status', 'dismiss');
  cy.setCookie('cookieconsent_status', 'dismiss');
  cy.get('body').then(($body) => {
    if ($body.find('button[aria-label="Close Welcome Banner"]').length > 0) {
      cy.get('button[aria-label="Close Welcome Banner"]').click({ force: true });
    }
    if ($body.find('a[aria-label="dismiss cookie message"]').length > 0) {
      cy.get('a[aria-label="dismiss cookie message"]').click({ force: true });
    }
  });
});

Cypress.Commands.add('visitWithBannersDismissed', (url: string) => {
  cy.setCookie('welcomebanner_status', 'dismiss');
  cy.setCookie('cookieconsent_status', 'dismiss');
  cy.visit(url, {
    onBeforeLoad(win) {
      const bid = win.localStorage.getItem('bid');
      if (bid) {
        win.sessionStorage.setItem('bid', bid);
      }
    },
  });
  cy.dismissInitialBanners();
});

Cypress.Commands.add(
  'registerByApi',
  (email: string, password = 'TestUser123!', securityAnswer = 'Mother Maiden Name') => {
    return cy
      .request({
        method: 'POST',
        url: '/api/Users/',
        body: {
          email,
          password,
          securityQuestion: {
            id: 1,
            question: 'Your eldest siblings middle name?',
            createdAt: '2026-01-01T00:00:00.000Z',
            updatedAt: '2026-01-01T00:00:00.000Z',
          },
          securityAnswer,
        },
      })
      .then((res) => {
        expect(res.status).to.eq(201);
        return res.body.data as RegisteredUser;
      });
  },
);

Cypress.Commands.add('loginByApi', (email = 'admin@juice-sh.op', password = 'admin123') => {
  return cy.session(
    [email, password],
    () => {
      cy.request({
        method: 'POST',
        url: '/rest/user/login',
        body: { email, password },
      }).then((res) => {
        expect(res.status).to.eq(200);
        const { token, bid, umail } = res.body.authentication;
        window.localStorage.setItem('token', token);
        window.localStorage.setItem('bid', String(bid));
        window.sessionStorage.setItem('bid', String(bid));
        window.localStorage.setItem('umail', umail);
        window.localStorage.setItem('welcomebanner_status', 'dismiss');
        window.localStorage.setItem('cookieconsent_status', 'dismiss');
      });
    },
    {
      validate() {
        cy.window().then((win) => {
          const token = win.localStorage.getItem('token');
          expect(token).to.be.a('string');
        });
      },
    },
  );
});

Cypress.Commands.add('addToBasketByApi', (productId: number, quantity = 1, token?: string) => {
  const authToken = token || window.localStorage.getItem('token') || '';
  const basketId = Number(window.localStorage.getItem('bid') || 1);

  return cy
    .request({
      method: 'POST',
      url: '/api/BasketItems/',
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
      body: {
        ProductId: productId,
        BasketId: basketId,
        quantity,
      },
    })
    .then((res) => {
      expect(res.status).to.eq(200);
      return res.body as BasketItemResponse;
    });
});
