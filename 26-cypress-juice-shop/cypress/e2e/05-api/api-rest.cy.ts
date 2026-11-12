describe('REST API - Core Endpoints', { tags: ['@smoke', '@regression'] }, () => {
  it('SC-API-01: GET /rest/products/search returns 200 and products list', () => {
    cy.request('GET', '/rest/products/search?q=').then((response) => {
      expect(response.status).to.eq(200);
      expect(response.body).to.have.property('status', 'success');
      expect(response.body.data).to.be.an('array').and.not.be.empty;

      const firstProduct = response.body.data[0];
      expect(firstProduct).to.have.all.keys(
        'id',
        'name',
        'description',
        'price',
        'deluxePrice',
        'image',
        'createdAt',
        'updatedAt',
        'deletedAt',
      );
    });
  });

  it('SC-API-02: POST /api/Users creates a disposable user', () => {
    const timestamp = Date.now();
    const dynamicEmail = `api-user-${timestamp}@test-juice.op`;

    cy.request('POST', '/api/Users/', {
      email: dynamicEmail,
      password: 'StrongPassword123!',
      securityQuestion: {
        id: 1,
        question: 'Your eldest siblings middle name?',
        createdAt: '2026-01-01T00:00:00.000Z',
        updatedAt: '2026-01-01T00:00:00.000Z',
      },
      securityAnswer: 'DisposAnswer',
    }).then((response) => {
      expect(response.status).to.eq(201);
      expect(response.body.status).to.eq('success');
      expect(response.body.data.email).to.eq(dynamicEmail);
      expect(response.body.data).to.have.property('id');
    });
  });

  it('SC-API-03: POST /rest/user/login authenticates and returns JWT token', () => {
    cy.request('POST', '/rest/user/login', {
      email: 'admin@juice-sh.op',
      password: 'admin123',
    }).then((response) => {
      expect(response.status).to.eq(200);
      expect(response.body).to.have.property('authentication');
      expect(response.body.authentication).to.have.property('token');
      expect(response.body.authentication.token).to.be.a('string');
      expect(response.body.authentication).to.have.property('bid');
      expect(response.body.authentication.umail).to.eq('admin@juice-sh.op');
    });
  });

  it('SC-API-04: GET /api/SecurityQuestions returns catalog of security questions', () => {
    cy.request('GET', '/api/SecurityQuestions/').then((response) => {
      expect(response.status).to.eq(200);
      expect(response.body).to.have.property('status', 'success');
      expect(response.body.data).to.be.an('array').and.have.length.greaterThan(0);
      expect(response.body.data[0]).to.have.property('question');
    });
  });
});
