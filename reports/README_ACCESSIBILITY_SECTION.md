## Accessibility

The Assistive Mirror integrates several accessibility features:

- High contrast HUD with semantic color tokens (`--ok`, `--warn`, `--err`, `--accent`).
- Typography clamps for large titles (`--title-size`) ensuring distant readability.
- Reduced motion support: respects OS `prefers-reduced-motion` and a server override (`reduce_motion` via `POST /settings`). Clients remove pulsing/slide animations when active.
- Keyboard demo shortcuts (1, 2, 3) generate local overlays for offline testing without camera/markers.
- Clear focus indicators (`:focus-visible` outline using accent color) in mock viewer and future interactive surfaces.

Enable reduced motion at runtime:
```bash
curl -X POST http://localhost:5055/settings -H 'Content-Type: application/json' -d '{"reduce_motion": true}'
```

The `/health` endpoint includes `reduce_motion` so UIs can synchronise animation state even if the OS preference allows motion.

See `ACCESSIBILITY.md` for full details and contribution guidelines.
