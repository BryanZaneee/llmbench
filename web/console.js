// llmbench: the two dithering shader backdrops, plus the dark-mode toggle.
// The page has no other client-side behavior of its own; main.js owns the
// leaderboard explorer.

import { mountBackdrop } from "/shared/backdrop.js";

// ── Page backdrop ──────────────────────────────────────────────────────
// Two near-identical paper tones dithering against each other, so the page
// reads as living paper rather than a flat fill. Theme-aware: the tones are
// re-sent when the toggle flips data-theme. Fixed and always on screen, so
// it skips the IntersectionObserver.
const PAGE_TONES = {
  light: { back: "#FAFAF7", front: "#F4F3ED" },
  dark: { back: "#0B0B0C", front: "#131316" },
};
const tones = () =>
  PAGE_TONES[document.documentElement.dataset.theme === "dark" ? "dark" : "light"];

const page = mountBackdrop(".page-flair", {
  ...tones(),
  pxSize: 3,
  scale: 0.35,
  speed: 0.08, // barely-there drift; it must never pull focus
  frame: 4000,
  observe: false,
});

// ── Hero band ──────────────────────────────────────────────────────────
// Same tuning as the llmbench row on the portfolio homepage, so the page
// and its work-index entry read as the same object. Dark in both themes,
// so it does not participate in the theme swap.
mountBackdrop(".lb-hero-flair", {
  back: "#081228",
  front: "#5A84E6",
  shape: 2, // warp
  type: 4, // 8x8 Bayer, finest grain
  pxSize: 2,
  observe: false,
});

// ── Dark-mode toggle ───────────────────────────────────────────────────
// Mirrors the main site's toggle and shares its localStorage key, so the
// theme follows the visitor between pages. The pre-paint script in <head>
// has already resolved the initial value.
const themeBtn = document.getElementById("theme-toggle");
if (themeBtn) {
  const paint = (theme) => {
    const dark = theme === "dark";
    document.documentElement.dataset.theme = theme;
    themeBtn.setAttribute("aria-pressed", String(dark));
    themeBtn.textContent = dark ? "☀" : "☾";
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = dark ? "#0B0B0C" : "#FAFAF7";
    const { back, front } = tones();
    page?.setColors(back, front);
  };
  paint(document.documentElement.dataset.theme);
  themeBtn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("bz-theme", next);
    paint(next);
  });
}
