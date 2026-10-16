import { Locator, Page } from '@playwright/test';
import { BasePage } from './BasePage';

export interface BillPayData {
  payeeName: string;
  street: string;
  city: string;
  state: string;
  zipCode: string;
  phoneNumber: string;
  accountNumber: string;
  verifyAccount?: string;
  amount: number;
}

export class BillPayPage extends BasePage {
  readonly payeeNameInput: Locator;
  readonly streetInput: Locator;
  readonly cityInput: Locator;
  readonly stateInput: Locator;
  readonly zipCodeInput: Locator;
  readonly phoneNumberInput: Locator;
  readonly accountNumberInput: Locator;
  readonly verifyAccountInput: Locator;
  readonly amountInput: Locator;
  readonly fromAccountSelect: Locator;
  readonly sendPaymentButton: Locator;
  readonly successResult: Locator;

  constructor(page: Page) {
    super(page);
    this.payeeNameInput = page.locator('input[name="payee.name"]');
    this.streetInput = page.locator('input[name="payee.address.street"]');
    this.cityInput = page.locator('input[name="payee.address.city"]');
    this.stateInput = page.locator('input[name="payee.address.state"]');
    this.zipCodeInput = page.locator('input[name="payee.address.zipCode"]');
    this.phoneNumberInput = page.locator('input[name="payee.phoneNumber"]');
    this.accountNumberInput = page.locator('input[name="payee.accountNumber"]');
    this.verifyAccountInput = page.locator('input[name="verifyAccount"]');
    this.amountInput = page.locator('input[name="amount"]');
    this.fromAccountSelect = page.locator('select[name="fromAccountId"]');
    this.sendPaymentButton = page.locator('input[value="Send Payment"]');
    this.successResult = page.locator('#billpayResult');
  }

  async goto(): Promise<void> {
    await this.page.goto('billpay.htm');
    await this.waitForPageLoad();
  }

  async payBill(data: BillPayData): Promise<void> {
    await this.payeeNameInput.waitFor({ state: 'visible' });
    await this.payeeNameInput.fill(data.payeeName);
    await this.streetInput.fill(data.street);
    await this.cityInput.fill(data.city);
    await this.stateInput.fill(data.state);
    await this.zipCodeInput.fill(data.zipCode);
    await this.phoneNumberInput.fill(data.phoneNumber);
    await this.accountNumberInput.fill(data.accountNumber);
    await this.verifyAccountInput.fill(data.verifyAccount ?? data.accountNumber);
    await this.amountInput.fill(data.amount.toFixed(2));
    await this.fromAccountSelect
      .locator('option')
      .first()
      .waitFor({ state: 'attached', timeout: 10000 });
    await this.sendPaymentButton.click();
    await this.successResult.waitFor({ state: 'visible', timeout: 10000 });
  }
}
