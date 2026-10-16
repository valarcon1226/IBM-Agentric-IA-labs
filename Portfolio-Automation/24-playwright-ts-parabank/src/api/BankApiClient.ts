import { APIRequestContext, APIResponse } from '@playwright/test';
import { Account, BillPayResult, Customer, LoanResponse, Payee, Transaction } from './types';

export class BankApiClient {
  private readonly request: APIRequestContext;
  private readonly baseUrl: string;

  constructor(request: APIRequestContext, baseUrl: string) {
    this.request = request;
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private apiPath(path: string): string {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}/services/bank${cleanPath}`;
  }

  async initializeDb(): Promise<APIResponse> {
    return this.request.post(this.apiPath('/initializeDB'));
  }

  async cleanDb(): Promise<APIResponse> {
    return this.request.post(this.apiPath('/cleanDB'));
  }

  async login(
    username: string,
    password: string,
  ): Promise<{ status: number; customer?: Customer; error?: string }> {
    const res = await this.request.get(
      this.apiPath(`/login/${encodeURIComponent(username)}/${encodeURIComponent(password)}`),
      {
        headers: { Accept: 'application/json' },
      },
    );
    const status = res.status();
    if (status === 200) {
      const customer = (await res.json()) as Customer;
      return { status, customer };
    }
    const error = await res.text();
    return { status, error };
  }

  async getCustomer(customerId: number): Promise<Customer> {
    const res = await this.request.get(this.apiPath(`/customers/${customerId}`), {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok()) {
      throw new Error(`Failed to get customer ${customerId}: HTTP ${res.status()}`);
    }
    return (await res.json()) as Customer;
  }

  async getCustomerAccounts(customerId: number): Promise<Account[]> {
    const res = await this.request.get(this.apiPath(`/customers/${customerId}/accounts`), {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok()) {
      throw new Error(`Failed to get accounts for customer ${customerId}: HTTP ${res.status()}`);
    }
    return (await res.json()) as Account[];
  }

  async getAccount(accountId: number): Promise<Account> {
    const res = await this.request.get(this.apiPath(`/accounts/${accountId}`), {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok()) {
      throw new Error(`Failed to get account ${accountId}: HTTP ${res.status()}`);
    }
    return (await res.json()) as Account;
  }

  async createAccount(
    customerId: number,
    newAccountType: 0 | 1,
    fromAccountId: number,
  ): Promise<Account> {
    const res = await this.request.post(
      this.apiPath(
        `/createAccount?customerId=${customerId}&newAccountType=${newAccountType}&fromAccountId=${fromAccountId}`,
      ),
      { headers: { Accept: 'application/json' } },
    );
    if (!res.ok()) {
      throw new Error(`Failed to create account: HTTP ${res.status()}`);
    }
    return (await res.json()) as Account;
  }

  async transfer(fromAccountId: number, toAccountId: number, amount: number): Promise<string> {
    const res = await this.request.post(
      this.apiPath(
        `/transfer?fromAccountId=${fromAccountId}&toAccountId=${toAccountId}&amount=${amount}`,
      ),
    );
    if (!res.ok()) {
      throw new Error(`Failed to transfer: HTTP ${res.status()}`);
    }
    return res.text();
  }

  async deposit(accountId: number, amount: number): Promise<string> {
    const res = await this.request.post(
      this.apiPath(`/deposit?accountId=${accountId}&amount=${amount}`),
    );
    if (!res.ok()) {
      throw new Error(`Failed to deposit: HTTP ${res.status()}`);
    }
    return res.text();
  }

  async withdraw(accountId: number, amount: number): Promise<string> {
    const res = await this.request.post(
      this.apiPath(`/withdraw?accountId=${accountId}&amount=${amount}`),
    );
    if (!res.ok()) {
      throw new Error(`Failed to withdraw: HTTP ${res.status()}`);
    }
    return res.text();
  }

  async requestLoan(
    customerId: number,
    amount: number,
    downPayment: number,
    fromAccountId: number,
  ): Promise<LoanResponse> {
    const res = await this.request.post(
      this.apiPath(
        `/requestLoan?customerId=${customerId}&amount=${amount}&downPayment=${downPayment}&fromAccountId=${fromAccountId}`,
      ),
      { headers: { Accept: 'application/json' } },
    );
    if (!res.ok()) {
      throw new Error(`Failed to request loan: HTTP ${res.status()}`);
    }
    return (await res.json()) as LoanResponse;
  }

  async getAccountTransactions(accountId: number): Promise<Transaction[]> {
    const res = await this.request.get(this.apiPath(`/accounts/${accountId}/transactions`), {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok()) {
      throw new Error(`Failed to get transactions for account ${accountId}: HTTP ${res.status()}`);
    }
    return (await res.json()) as Transaction[];
  }

  async getTransaction(transactionId: number): Promise<Transaction> {
    const res = await this.request.get(this.apiPath(`/transactions/${transactionId}`), {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok()) {
      throw new Error(`Failed to get transaction ${transactionId}: HTTP ${res.status()}`);
    }
    return (await res.json()) as Transaction;
  }

  async billPay(accountId: number, amount: number, payee: Payee): Promise<BillPayResult> {
    const res = await this.request.post(
      this.apiPath(`/billpay?accountId=${accountId}&amount=${amount}`),
      {
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        data: payee,
      },
    );
    if (!res.ok()) {
      throw new Error(`Failed to billpay: HTTP ${res.status()}`);
    }
    return (await res.json()) as BillPayResult;
  }
}
