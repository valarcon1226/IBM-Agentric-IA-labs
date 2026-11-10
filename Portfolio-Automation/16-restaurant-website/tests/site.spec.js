const { test, expect } = require('@playwright/test');
const { execSync } = require('child_process');

test.describe('Sabor de Casa website tests', () => {
  const pages = [
    '/',
    '/inicio/',
    '/menu/',
    '/reservas/',
    '/domicilios/',
    '/contacto/',
    '/politica-de-privacidad/',
    '/eventos-y-catering/'
  ];

  for (const page of pages) {
    test(`Page ${page} responds with 200 and loads`, async ({ request, page: browserPage }) => {
      const response = await request.get(`http://localhost:8016${page}`);
      expect(response.status()).toBe(200);
      
      await browserPage.goto(`http://localhost:8016${page}`);
      await expect(browserPage.locator('body')).toBeVisible();
    });
  }

  test('Formulario de reservas real', async ({ page, request }) => {
    // Clear Mailpit inbox
    await request.delete('http://localhost:8025/api/v1/messages');

    await page.goto('http://localhost:8016/reservas/');

    // Select Party size FIRST because changing it clears the date/time pickers!
    await page.selectOption('select[name="rtb-party"]', '4');
    await page.fill('input[name="rtb-name"]', 'Test User Reserva');
    await page.fill('input[name="rtb-email"]', 'testreserva@example.com');
    await page.fill('input[name="rtb-phone"]', '3001234567');

    await page.fill('#rtb-date', '2025-12-01');
    await page.selectOption('#rtb-time', '13:00');

    await expect(page.locator('#rtb-date')).toHaveValue('2025-12-01');
    await expect(page.locator('#rtb-time')).toHaveValue('13:00');

    await page.click('button[type="submit"]');
    await expect(page.locator('.rtb-message')).toBeVisible({ timeout: 10000 });

    // Check mailpit
    await expect(async () => {
        const emailsRes = await request.get('http://localhost:8025/api/v1/messages');
        const emails = await emailsRes.json();
        expect(emails.messages.length).toBeGreaterThan(0);
    }).toPass();
    const emailsRes = await request.get('http://localhost:8025/api/v1/messages');
    const emails = await emailsRes.json();
    const hasSaborDeCasaEmail = emails.messages.some(m => m.Subject.includes('Sabor de Casa') || m.From.Name === 'Sabor de Casa');
    expect(hasSaborDeCasaEmail).toBe(true);
    
    // Check with wp-cli via docker exec
    const bookings = execSync('docker exec sabor-wpcli wp post list --post_type=rtb-booking --format=json').toString();
    const bookingsArray = JSON.parse(bookings);
    const myBooking = bookingsArray.find(b => b.post_title.includes('Test User Reserva') || b.post_title.includes('testreserva@example.com'));
    expect(myBooking).toBeDefined();
  });

  test('Formulario de eventos envia email a mailpit', async ({ page, request }) => {
    await request.delete('http://localhost:8025/api/v1/messages');
    await page.goto('http://localhost:8016/eventos-y-catering/');
    
    // Fill CF7 custom form
    await page.fill('input[name="event-type"]', 'Boda');
    await page.fill('input[name="event-date"]', '2025-12-01');
    await page.fill('input[name="guests"]', '50');
    await page.fill('input[name="your-name"]', 'Evento User');
    await page.fill('input[name="your-email"]', 'evento@example.com');
    await page.fill('input[name="your-phone"]', '3009876543');
    
    await page.click('input[type="submit"]');

    // CF7 success message
    await expect(page.locator('.wpcf7-response-output')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.wpcf7-response-output')).toContainText('Thank you', { ignoreCase: true });

    // Check mailpit
    await expect(async () => {
        const emailsRes = await request.get('http://localhost:8025/api/v1/messages');
        const emails = await emailsRes.json();
        expect(emails.messages.length).toBeGreaterThan(0);
    }).toPass();
  });
});
