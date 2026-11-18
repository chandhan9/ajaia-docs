// Browser smoke test of every core flow (login, format, persist, share, import,
// viewer restrictions, edit conflict). Needs a FRESH database (it expects the seed data).
//   npm i -D playwright && npx playwright install chromium
//   DATABASE_PATH=/tmp/e2e.db PORT=5055 python wsgi.py   # in another terminal
//   BASE_URL=http://localhost:5055 node tests/e2e/browser-smoke.js
const path = require('path');
const { chromium } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:5055';
const ROOT = path.resolve(__dirname, '..', '..');
const SHOTS = path.join(ROOT, 'docs', 'screenshots');
const SAMPLES = path.join(ROOT, 'sample-files');
const assert = (c, m) => { if (!c) throw new Error('ASSERT: ' + m); console.log('ok -', m); };

async function login(page, name) {
  await page.goto(BASE + '/');
  await page.getByRole('button', { name: new RegExp('^' + name) }).click();
  await page.getByText('My documents').waitFor();
}
async function saved(page) { await page.locator('.save-status', { hasText: 'All changes saved' }).waitFor({ timeout: 5000 }); }

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  const mk = async () => { const c = await browser.newContext({ viewport: { width: 1280, height: 860 } });
    const p = await c.newPage(); p.on('pageerror', e => errors.push(e.message));
    p.on('console', m => m.type() === 'error' && !m.text().startsWith('Failed to load resource') && errors.push(m.text())); return p; };

  const a = await mk();
  await a.goto(BASE + '/'); await a.screenshot({ path: `${SHOTS}/01-login.png` });
  await login(a, 'Alice');

  // create + format
  await a.getByRole('button', { name: '+ New document' }).click();
  await a.locator('#editor').waitFor();
  await a.locator('.title-input').fill('Launch plan');
  const ed = a.locator('#editor'); await ed.click();
  await a.getByRole('button', { name: 'Heading 1' }).click();
  await a.keyboard.type('Launch plan'); await a.keyboard.press('Enter');
  await a.getByRole('button', { name: 'Normal text' }).click();
  await a.keyboard.type('We ship ');
  await a.getByRole('button', { name: 'Bold (Ctrl/Cmd+B)' }).click(); await a.keyboard.type('Friday');
  await a.getByRole('button', { name: 'Bold (Ctrl/Cmd+B)' }).click(); await a.keyboard.type(' with ');
  await a.keyboard.press('Control+i'); await a.keyboard.type('care'); await a.keyboard.press('Control+i');
  await a.keyboard.press('Control+u'); await a.keyboard.type(' today'); await a.keyboard.press('Control+u');
  await a.keyboard.press('Enter');
  await a.getByRole('button', { name: 'Bulleted list' }).click();
  await a.keyboard.type('Docs'); await a.keyboard.press('Enter'); await a.keyboard.type('Tests');
  await a.keyboard.press('Enter'); await a.keyboard.press('Enter');
  await a.getByRole('button', { name: 'Numbered list' }).click();
  await a.keyboard.type('Deploy'); 
  await saved(a);
  await a.locator('#editor b, #editor strong').first().click(); await a.evaluate(() => window.scrollTo(0, 0)); await a.screenshot({ path: `${SHOTS}/03-editor-formatting.png` });
  const url = a.url();

  // reload -> persisted
  await a.reload(); await a.locator('#editor h1').waitFor();
  const html = await ed.innerHTML();
  console.log(html);
  assert(await a.locator('.title-input').inputValue() === 'Launch plan', 'title persisted');
  for (const f of ['<h1>Launch plan</h1>', '<strong>Friday</strong>', '<em>care</em>', 'today</u>', '<li>Docs</li>', '<ol><li>Deploy</li></ol>'])
    assert(html.includes(f), 'persisted ' + f);

  // share with carol as viewer
  await a.getByRole('button', { name: 'Share' }).click();
  await a.locator('#share-email').fill('carol@ajaia.test');
  await a.locator('#share-role').selectOption('viewer');
  await a.locator('#share-submit').click();
  await a.locator('#share-list', { hasText: 'Carol Viewer' }).waitFor();
  await a.locator('#share-email').fill('ghost@ajaia.test'); await a.locator('#share-submit').click();
  await a.locator('#share-error', { hasText: 'No user' }).waitFor();
  assert(true, 'share validation error shown');
  await a.screenshot({ path: `${SHOTS}/04-share-dialog.png` });
  await a.locator('#share-close').click();

  // import files from home
  await a.goto(BASE + '/#/');
  for (const f of ['meeting-notes.md', 'q4-hiring-plan.docx', 'release-checklist.txt']) {
    await a.getByText('My documents').waitFor();
    const [chooser] = await Promise.all([a.waitForEvent('filechooser'), a.getByRole('button', { name: 'Import file' }).click()]);
    await chooser.setFiles(`${SAMPLES}/${f}`);
    await a.locator('#editor').waitFor();
    await a.waitForFunction(() => document.querySelector('#editor').textContent.length > 10);
    if (f.endsWith('.docx')) { assert(await a.locator('#editor h1', { hasText: 'Q4 Hiring Plan' }).count() === 1, 'docx heading imported');
      await a.screenshot({ path: `${SHOTS}/05-imported-docx.png` }); }
    await a.goto(BASE + '/#/');
  }
  // unsupported import
  await a.getByText('My documents').waitFor();
  const [ch2] = await Promise.all([a.waitForEvent('filechooser'), a.getByRole('button', { name: 'Import file' }).click()]);
  await ch2.setFiles({ name: 'x.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF') });
  await a.locator('#toast', { hasText: 'Unsupported file type' }).waitFor();
  assert(true, 'unsupported file rejected with message');
  await a.locator('.doc-card', { hasText: 'meeting-notes' }).waitFor();
  await a.screenshot({ path: `${SHOTS}/02-home-alice.png` });

  // insert file into existing doc
  await a.goto(url); await a.locator('#editor h1').waitFor();
  await a.locator('#editor ol li').click();
  await a.keyboard.press('End'); await a.keyboard.press('Enter'); await a.keyboard.press('Enter');
  const [ch3] = await Promise.all([a.waitForEvent('filechooser'), a.getByRole('button', { name: /Insert file/ }).click()]);
  await ch3.setFiles(`${SAMPLES}/release-checklist.txt`);
  await a.locator('#editor', { hasText: 'Deploy to staging' }).waitFor(); await saved(a);
  assert(true, 'insert file into existing doc');

  // carol: shared, view only
  const c = await mk(); await login(c, 'Carol');
  const sharedCards = c.locator('h2:has-text("Shared with me") + .doc-grid .doc-card');
  assert(await sharedCards.count() === 2, 'carol sees 2 shared docs');
  await c.screenshot({ path: `${SHOTS}/06-home-carol-shared.png` });
  await c.locator('.doc-card', { hasText: 'Launch plan' }).click();
  await c.locator('.readonly-note').waitFor();
  assert(await c.locator('#editor').getAttribute('contenteditable') === 'false', 'viewer cannot edit');
  assert(await c.getByRole('button', { name: 'Share' }).count() === 0, 'viewer has no share button');
  await c.screenshot({ path: `${SHOTS}/07-viewer-readonly.png` });

  // conflict: alice and bob both edit the welcome doc
  const b = await mk(); await login(b, 'Bob');
  await b.locator('.doc-card', { hasText: 'Welcome' }).click(); await b.locator('#editor h1').waitFor();
  await a.goto(BASE + '/#/'); await a.locator('.doc-card', { hasText: 'Welcome' }).click(); await a.locator('#editor h1').waitFor();
  await b.locator('#editor h1').click(); await b.keyboard.press('End'); await b.keyboard.type(' (Bob)'); await saved(b);
  await a.locator('#editor h1').click(); await a.keyboard.press('End'); await a.keyboard.type(' (Alice)');
  await a.locator('.banner', { hasText: 'saved a newer version' }).waitFor();
  assert(true, 'conflict banner shown');
  await a.screenshot({ path: `${SHOTS}/08-conflict.png` });
  await a.getByRole('button', { name: 'Load their version' }).click();
  assert((await a.locator('#editor h1').textContent()).includes('(Bob)'), 'loaded latest version');

  // logout
  await c.getByRole('button', { name: 'Sign out' }).click(); await c.getByText('Demo accounts').waitFor();
  assert(errors.length === 0, 'no console errors: ' + errors.join(' | '));
  await browser.close();
  console.log('E2E PASSED');
})().catch(e => { console.error(e); process.exit(1); });
