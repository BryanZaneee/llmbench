# README screenshots

From the repository root, after installing the application's dependencies:

```sh
cd docs/screenshots && npm ci && npx playwright install chromium && npm run capture
```

Requires Node.js, Python 3 for static previews, and `cwebp` (libwebp).
Each capture starts and stops its own loopback preview. It uses a fresh browser,
fixture data, a fixed date, and a 1440 × 960 viewport. External requests are blocked;
the CLI and test output is produced by the local `.venv/bin/python` installation. The images show the actual UI,
not proof of backend or provider behavior. Images are WebP, below 300 KB.

Application runtime dependencies are unchanged by this separate tooling package.
