// Checks that a browser is available for headless rendering. Exit 0 = ready.
import {launchBrowser} from './render.mjs';

try {
  const browser = await launchBrowser();
  const version = browser.version();
  await browser.close();
  console.log(`ok ${version}`);
} catch (e) {
  console.log(String(e.message || e).split('\n')[0]);
  process.exit(1);
}
