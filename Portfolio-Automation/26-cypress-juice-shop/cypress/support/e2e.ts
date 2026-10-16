// @ts-expect-error - @cypress/grep exports function
import registerCypressGrep from '@cypress/grep';
registerCypressGrep();

import './commands';

// Ignore uncaught third-party / UI exceptions from Juice Shop so tests do not fail on benign app issues
Cypress.on('uncaught:exception', (err) => {
  if (
    err.message.includes('Script error') ||
    err.message.includes('ResizeObserver') ||
    err.message.includes('Cannot read property') ||
    err.message.includes('Cannot read properties')
  ) {
    return false;
  }
  return true;
});
