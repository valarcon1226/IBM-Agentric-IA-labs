// Edge, not the bundled Chromium.
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  use: { channel: 'msedge' },
});
