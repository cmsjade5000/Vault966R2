# Vault 966 iPad Landscape Audit

## Device

- iPad Air 2 (`iPad5,3`) on iPadOS 15.8.8
- Safari 15.6.8 / WebKit 605.1.15
- Landscape viewport observed at 1024 x 698 CSS pixels
- Device pixel ratio 2, coarse pointer, 5 touch points
- App served from the Mac over local HTTP

## Verified

- Library has no horizontal overflow at 1024 CSS pixels.
- Library retains four columns in landscape.
- Desktop top navigation remains visible and bottom navigation remains hidden.
- Library controls targeted by the plan measure at least 44 x 44 CSS pixels.
- Discover has no horizontal overflow.
- Discover rail links were updated to a 44-pixel minimum touch height.
- The passwordless local unlock flow was completed in Safari on the connected iPad.
- Watchlist loaded at 1024 x 698 with no horizontal overflow and retained desktop navigation.
- The Library filter panel opens correctly on the connected iPad.
- Custom year and runtime fields were increased from approximately 30 to 44 CSS pixels.
- Like and Watchlist pills, detail back links, external badges, and carousel controls now use
  the 44-pixel coarse-pointer target rules.
- Modern iPadOS detection recognizes `MacIntel` with touch capability.
- Traditional iPad user agents, desktop Safari, and standalone mode are covered by JavaScript tests.
- Manifest uses landscape orientation.
- The iPad Air 2 landscape startup image exists and is referenced by the base template.
- Clipboard behavior remains feature-detected with the existing non-clipboard fallback.
- No service worker, offline cache, HTTPS setup, or container-query dependency was added.

## Automated Results

- Python: 229 passed, 1 expected failure.
- JavaScript: 4 passed.
- Added JavaScript files pass Prettier checks.
- Repository-wide Prettier still reports existing formatting differences in `base.js`,
  `discover_refresh.js`, and `movies_page.js`.
- `git diff --check` passes.

## Remaining Physical Checks

- Add to Home Screen launch, startup image, safe-area spacing, and return from background.
- End-to-end physical touch operation for Like, Watchlist, sorting, and detail actions after
  Remote Automation is re-enabled on the iPad.

Direct iPad screenshots were unavailable because Developer Mode and the developer disk image
are not enabled on the device. Those settings were intentionally left unchanged.
