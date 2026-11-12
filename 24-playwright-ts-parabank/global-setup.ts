import { request } from '@playwright/test';
import { BASE_URL } from './playwright.config';
import { BankApiClient } from './src/api/BankApiClient';

// A fresh ParaBank container has no seed customers until initializeDB runs.
export default async function globalSetup(): Promise<void> {
  const context = await request.newContext();
  try {
    const res = await new BankApiClient(context, BASE_URL).initializeDb();
    if (!res.ok()) {
      throw new Error(`initializeDB failed before the run: HTTP ${res.status()}`);
    }
  } finally {
    await context.dispose();
  }
}
