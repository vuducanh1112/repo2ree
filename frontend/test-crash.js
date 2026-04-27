const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ 
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    headless: false 
  });
  const page = await browser.newPage();
  await page.goto('http://localhost:5173/');
  await page.pause(); // This opens the "Codegen" Inspector window
})();