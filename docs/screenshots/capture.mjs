import { execFileSync } from 'node:child_process';
import { capture, repo } from './capture-lib.mjs';
const escape = s => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
const python = `${repo}/.venv/bin/python`;
await capture({
  command: 'python3', args: ['-m', 'http.server', '9413', '--bind', '127.0.0.1'], port: 9413,
  async shots(page, origin, shoot) {
    for (const [name, label, args] of [
      ['leaderboard', 'llmbench leaderboard --source bundled --offline --top 10', ['-m', 'llmbench.cli', 'leaderboard', '--source', 'bundled', '--offline', '--top', '10']],
      ['tests', 'python -m pytest -q', ['-m', 'pytest', '-q']]
    ]) {
      const output = execFileSync(python, args, { cwd: repo, encoding: 'utf8', env: { ...process.env, NO_COLOR: '1', COLUMNS: '100' } });
      await page.setContent(`<style>body{margin:0;padding:48px;background:#f7f7f2;color:#202428;font:18px/1.7 monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><pre>$ ${escape(label)}\n\n${escape(output.replaceAll(repo, '.'))}</pre>`);
      await shoot(name);
    }
  }
});
