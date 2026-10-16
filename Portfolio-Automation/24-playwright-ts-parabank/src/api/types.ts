export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
}

export interface Customer {
  id: number;
  firstName: string;
  lastName: string;
  address: Address;
  phoneNumber: string;
  ssn: string;
}

export type AccountType = 'CHECKING' | 'SAVINGS' | 'LOAN';

export interface Account {
  id: number;
  customerId: number;
  type: AccountType;
  balance: number;
}

export type TransactionType = 'Credit' | 'Debit';

export interface Transaction {
  id: number;
  accountId: number;
  type: TransactionType;
  date: number;
  amount: number;
  description: string;
}

export interface BillPayResult {
  payeeName: string;
  amount: number;
  accountId: number;
}

export interface LoanResponse {
  responseDate: string;
  loanProviderName: string;
  approved: boolean;
  message?: string | null;
  accountId?: number;
}

export interface Payee {
  name: string;
  address: Address;
  phoneNumber: string;
  accountNumber: number;
}
