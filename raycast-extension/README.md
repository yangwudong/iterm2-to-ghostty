# Ghostty Profiles — Raycast Extension

A Raycast extension that turns your exported iTerm2 profiles into a searchable
launcher for [Ghostty](https://ghostty.org): open SSH sessions, directories, or
commands in Ghostty tabs, reorder them, and re-sync from iTerm2 — all from Raycast.

It reads `~/.config/ghostty/profiles.json`, which is produced by the Python
export script in the repo root (`iterm2_to_ghostty.py --export-profiles-json`).

## Prerequisites

- **macOS** (Raycast, Ghostty, and iTerm2's plist are macOS-only)
- [Raycast](https://raycast.com) installed
- [Ghostty](https://ghostty.org) installed at `/Applications/Ghostty.app`
- [iTerm2](https://iterm2.com) with your profiles (the source of truth)
- **Node.js 22+** (only for installing / developing the extension)
- **Python 3** (macOS Command Line Tools' `python3` is fine — used by the export script)

## One-time setup

```bash
git clone git@github.com:yangwudong/iterm2-to-ghostty.git
cd iterm2-to-ghostty/raycast-extension
npm install
npm run dev
```

`npm run dev` runs once to **import** the extension into Raycast. Then:

1. Open Raycast and confirm **Ghostty Profiles** and **Reorder Ghostty Profiles**
   appear at the top of the root search.
2. Set the script-path preference: **Raycast → Settings → Extensions →
   Ghostty Profiles → `scriptPath`** → point it at the repo's
   `iterm2_to_ghostty.py` (e.g. `/Users/<you>/code/iterm2-to-ghostty/iterm2_to_ghostty.py`).
3. Back in the terminal, press **Ctrl+C** to stop the dev server.

The extension **stays installed** in Raycast after Ctrl+C — you do **not** need
`npm run dev` for daily use. It only needs to run again when you change the
source code (see [Updating](#updating-after-code-changes)).

## First export (generate profiles.json)

The extension reads `~/.config/ghostty/profiles.json`. Generate it once, either:

- **From a terminal** (repo root):
  ```bash
  ./iterm2_to_ghostty.py --export-profiles-json
  ```
- **From Raycast**: open **Ghostty Profiles**, scroll to the bottom, select
  **`*** Sync Profiles ***`**, press Enter — it opens Ghostty and runs the
  export in a login shell, leaving the tab open so you can see the result.

## Daily usage

| Command | What it does |
|---|---|
| **Ghostty Profiles** | Search by name / host / tag; **Enter** opens a Ghostty tab (SSH / directory / command). **⌘K** for more actions: new window, copy command, reveal directory. |
| **Reorder Ghostty Profiles** | Set your own order: **⌘U** / **⌘D** move up/down, **⌥⌘U** / **⌥⌘D** to top/bottom, **⇧⌘R** reset to alphabetical. Persists to `profiles.json` on every move. |
| **`*** Sync Profiles ***`** (inside Ghostty Profiles) | Re-export from iTerm2 after editing/adding profiles there. |

After syncing, press **Refresh** in the Ghostty Profiles command to reload.

Search results **preserve your custom order** (the extension filters itself,
rather than letting Raycast re-sort by relevance).

## The workflow

```
iTerm2 (edit/add profiles)
   │
   │  *** Sync Profiles *** entry  (or: ./iterm2_to_ghostty.py --export-profiles-json)
   ▼
profiles.json  (~/.config/ghostty/profiles.json)
   │
   │  Raycast reads it
   ▼
Ghostty Profiles  (search / launch / reorder)
```

The export **preserves your custom order** across re-syncs; profiles newly added
in iTerm2 land at the bottom, in iTerm2's own profile order.

## Updating after code changes

```bash
cd iterm2-to-ghostty/raycast-extension
npm run dev      # hot-reloads on save (Raycast → Settings → Advanced → "Auto-reload on save")
# Ctrl+C when done — the updated extension stays installed
```

## Notes & troubleshooting

- **Don't move or delete the source directory.** The installed extension
  references `raycast-extension/`. If you relocate the repo, re-run `npm run dev`
  from the new path.
- **`profiles.json` location**: `~/.config/ghostty/profiles.json`. The extension
  reads it; the Reorder command writes only its `order` field (everything else is
  owned by the export script).
- **Shortcuts are Raycast-scoped** — they fire only while a command's window is
  open and never conflict with OS-wide hotkeys.
- **A stale command lingering in Raycast after a rename** (e.g. an old
  "Search Ghostty Profiles"): remove it via Raycast → Settings → Extensions.
- **`scriptPath` not set**: the `*** Sync Profiles ***` entry shows a toast and
  opens the command preferences for you.

## Development

```bash
# Python tests (from repo root)
python3 -m unittest discover -s tests

# TypeScript tests + type-check (from raycast-extension/)
npm test
npx tsc --noEmit
```

Design specs and implementation plans live under `docs/superpowers/`.
