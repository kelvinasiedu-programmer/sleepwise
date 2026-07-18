# Accessibility checklist (WCAG 2.1 AA target)

This is the working checklist for SleepWise's front end. Items marked done are
implemented and covered by tests or a documented manual check; nothing here is
aspirational hand-waving.

## Semantic structure and landmarks

- [x] One `<h1>` per page, headings in order (h1 > h2 > h3, no skips)
- [x] Landmarks: `<header>`, `<nav>`, `<main id="main">`, `<footer>` on every page
- [x] Duplicate landmarks distinguished: `aria-label="Primary"` on the header nav,
      `aria-label="Footer"` on the footer nav
- [x] Skip link ("Skip to main content") as the first focusable element on every page
- [x] `lang="en"` on the root element
- [x] Results container is a labeled region (`role="region"`, `aria-label="Results"`)

## Keyboard

- [x] Everything operable by keyboard alone: form, chips (Enter adds, Backspace removes),
      checkboxes, buttons, links
- [x] Visible focus indicator on every interactive element (`:focus-visible` outline in
      the accent color, offset so it never blends into the control)
- [x] No keyboard traps; chip remove buttons are real `<button>` elements with
      `aria-label="Remove <name>"`
- [x] Logical tab order follows the visual order (no positive tabindex anywhere)

## Color and contrast

- [x] Light mode text tones checked against the white background: body 15.4:1, muted
      gray 4.7:1 (passes AA for the small text it is used on)
- [x] Dark mode link color fixed: the light-mode accent measured about 2.6:1 on the
      dark background, a real AA failure. Dark mode now uses a lightened accent
      (about 7:1 for links) and flips button text to dark (about 6.9:1)
- [x] Status pills (Lower concern / Use caution / Ask a clinician first) pair dark text
      on light tints in both schemes
- [x] Meaning is never conveyed by color alone: pills carry text labels, warnings carry
      a severity prefix, blocked items are in a separately headed section
- [x] Honors `prefers-color-scheme` for dark mode and `prefers-reduced-motion`
      (animations, transitions, and smooth scrolling all disabled)

## Forms and dynamic content

- [x] Every input has a programmatic `<label for>`; checkbox group uses
      `role="group"` with `aria-labelledby`
- [x] Status line uses `aria-live="polite"`; errors add `role="alert"`
- [x] After a check completes, "Results ready below." is announced (the region itself is
      not a live region, so screen readers are not flooded with every card at once)
- [x] Submit button disabled while a request is in flight (no double submits)
- [x] Autocomplete via native `<datalist>` (keyboard and screen-reader friendly for
      free) with free text always accepted

## Mobile

- [x] Mobile-first single-column layout; no horizontal scroll at 375 px
- [x] Text is readable without zoom; viewport meta does not disable zoom
- [x] Checkbox and chip targets wrap cleanly on narrow screens

## Click-depth audit

- Example result: 1 click ("Try an example" on the homepage)
- Personal result: type meds, 1 click ("Check my supplements")
- Any content page to a personal check: 1 click (checker link on every page)
- Printable pharmacist report from results: 1 click ("Print report")

There is no consultation booking. SleepWise is an educational checker, not a telehealth
service; its endpoint is a better-prepared pharmacist conversation, which is what the
report supports.

## How this is verified

- Automated: Lighthouse accessibility (98 at last run), axe-style checks via the
  landmark/label assertions in `tests/test_api.py` and `tests/test_pages.py`
- Manual: keyboard-only walkthrough of the full check flow, dark and light schemes,
  375 px viewport pass
- Contrast ratios computed against WCAG relative-luminance math when tokens change

Report accessibility problems through the
[issue tracker](https://github.com/kelvinasiedu-programmer/sleepwise/issues); they are
treated as bugs, not enhancements.
