import { chromium } from '@playwright/test';
import { execFileSync, spawn } from 'node:child_process';
import { statSync, unlinkSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
export const repo = path.resolve(here, '../..');

// A fresh browser context never reads personal cookies or local storage.
export async function capture({ command, args = [], port, setup = async () => {}, shots }) {
  execFileSync('cwebp', ['-version'], { stdio: 'ignore' });
  const origin = `http://127.0.0.1:${port}`;
  // Refuse an occupied port instead of photographing an unrelated local service.
  if (await fetch(origin).then(() => true, () => false)) throw new Error(`Port ${port} is occupied`);
  const server = spawn(command, args, { cwd: repo, stdio: ['ignore', 'pipe', 'pipe'], detached: true });
  let logs = '';
  server.stdout.on('data', b => { logs = (logs + b).slice(-4000); });
  server.stderr.on('data', b => { logs = (logs + b).slice(-4000); });
  let browser;
  try {
    let ready = false;
    for (let i = 0; i < 180; i++) {
      if (server.exitCode !== null) throw new Error(`Preview stopped: ${logs}`);
      if (await fetch(origin).then(r => r.ok, () => false)) { ready = true; break; }
      await new Promise(r => setTimeout(r, 500));
    }
    if (!ready) throw new Error(`Preview did not start: ${logs}`);
    browser = await chromium.launch();
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, reducedMotion: 'reduce', colorScheme: 'light', timezoneId: 'UTC', locale: 'en-US' });
    // All fixture captures are local; no authenticated services or paid APIs.
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await setup(context, origin);
    const page = await context.newPage();
    await page.clock.setFixedTime(new Date('2026-10-04T12:00:00Z'));
    const shoot = async name => {
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: path.join(here, `${name}.png`), animations: 'disabled' });
      const png = path.join(here, `${name}.png`), out = path.join(here, `${name}.webp`);
      for (const quality of [82, 65, 45]) {
        execFileSync('cwebp', ['-quiet', '-q', String(quality), png, '-o', out]);
        if (statSync(out).size < 300000) { unlinkSync(png); console.log(name); return; }
      }
      throw new Error(`${name} exceeds 300 KB`);
    };
    await shots(page, origin, shoot);
  } finally {
    await browser?.close();
    try { process.kill(-server.pid, 'SIGTERM'); } catch {}
  }
}
