# Frontend Restore Notes

## Provenance

- Original upstream repo: `https://github.com/brokermr810/QuantDinger`
- Last public frontend source commit: `ffdd2ffbae99cd77f90c9c9facd6f290d033dd2b`
- Commit date: February 27, 2026
- Commit that removed public frontend source: `abbad97bddfb1b3e72275f07158f8e30290b5a37`
- Removal date: February 27, 2026

## What This Folder Is

`frontend_vue` is a reconstructed editable frontend source tree created from the last public source commit before the project switched to a prebuilt private frontend.

It is intended to be:

- a full Vue source tree you can modify
- much closer to the official project than the older `feature/multi-user-postgresql` import
- compatible enough to build locally against the current backend layout

## What It Is Not

Because the newer frontend is only published as [`frontend/dist`](/e:/DinQuant/frontend/dist) and does not include source maps, this folder cannot be proven identical to the private 3.0.1 source used to produce that bundle.

In practice:

- `frontend_vue` is the last verifiable public source
- `frontend/dist` is the latest bundled UI artifact
- newer UI changes after February 27, 2026 must be inferred manually from the bundle

## Verification Done Locally

The restored source was verified with:

```bash
cd frontend_vue
corepack yarn install --ignore-engines
corepack yarn build
```

The build completed successfully on April 6, 2026 in this workspace.

## Recommended Workflow

1. Use `frontend_vue` as your editable source tree.
2. Keep `frontend/dist` as the behavioral reference for the newer private frontend.
3. When you need parity with a specific screen in `frontend/dist`, port it screen-by-screen into `frontend_vue`.

## Current Limitation

The rebuilt `frontend_vue/dist` is buildable, but its generated asset set does not exactly match the official `frontend/dist` asset hashes and chunk layout. That is expected because the official frontend continued evolving privately after the public source was removed.
