# Profile Custom Ordering — Design Spec

- **Date:** 2026-07-05
- **Status:** Approved (brainstorming complete), pending implementation plan
- **Parent project:** `2026-07-05-iterm-ghostty-raycast-design.md` (the iTerm→Ghostty Raycast extension this extends)
- **Goal:** Let the user define a custom display order for ALL exported profiles, editable from within Raycast, that survives re-export and gracefully accommodates profiles added later.

## 1. Problem & Constraints

The base extension lists profiles in the order they come out of `profiles.json` (currently id-sorted). The user wants to set the order themselves. Constraints established in brainstorming:

- **No frecency / auto-learning** — explicit, user-controlled order only.
- **Full ordering** — the user wants to order all ~78 profiles, not just pin favorites.
- **Editable from within Raycast** — via a dedicated Reorder command (Raycast's `List` does not support drag-and-drop, so reordering uses Move actions).
- **Future-proof** — adding profiles in iTerm2 and re-exporting must NOT wipe the custom order; new profiles land at the bottom.
- **Single source of truth** — the order lives inside `profiles.json` (one file to back up / version), not a separate file.
- **Selection retention** — after a Move re-renders the list, the cursor stays on the moved item so the user can repeat-move it (e.g. hold ⌥ and mash ↑).
- **Shortcuts scoped to Raycast** — action shortcuts are command-scoped (Raycast's default behavior), not OS-global hotkeys; they must not conflict with system shortcuts.

## 2. Architecture (chosen: order inside profiles.json)

The order is a top-level `order: string[]` field added to `profiles.json`, making the file the single source of truth for both data and ordering.

```
iTerm2 plist ──export script──▶ profiles.json { profiles:[...], order:[ids] }
                                          ▲               ▲
                                          │               │
            Reorder command writes only the order field ──┘
            (read-modify-write, preserves profiles data)
                                          │
            Main command + Reorder command both READ order to sort ──▶ UI
```

- The **export script** is the only writer of the `profiles` array; it MERGES the existing `order` across re-exports.
- The **Reorder command** is the only writer of the `order` field; it preserves `profiles` untouched.
- Both do full read-modify-write of `profiles.json`, each preserving the other's field. The user never hand-edits the file.

Rejected alternatives: separate `profile-order.json` (two files to back up); Raycast LocalStorage (not portable across machines/reinstalls).

## 3. `profiles.json` schema change

Add a top-level `order` field, peer of `profiles`:

```json
{
  "schema_version": 1,
  "exported_at": "2026-07-05T12:00:00Z",
  "source": "com.googlecode.iterm2",
  "order": ["nas", "perficient-pc-ubuntu", "ai-ollama-deepseek-32b"],
  "profiles": [ ... unchanged shape ... ]
}
```

- `schema_version` stays `1`. The loader treats a missing `order` as empty (backward compatible with files produced by the base project).
- `order` is an array of profile ids (the stable slug produced by `slugify_id`). Each id SHOULD appear at most once; duplicates are ignored after the first occurrence during sort.

## 4. Sort & merge rules

### 4.1 Display sort (used by both the main command and the Reorder command)

Given `profiles` and `order`, render order is:

1. For each id in `order` (in array order), if a profile with that id exists, emit it.
2. Then emit any profiles whose id is NOT in `order`, sorted alphabetically by `name` (stable fallback).
3. Duplicate ids in `order` are ignored after the first occurrence.

This makes the view fully determined by `order` + the profiles set. When `order` is empty/absent, everything falls through to step 2 → alphabetical by name.

### 4.2 Export-script merge (in `build_profiles_document`)

Before overwriting `profiles.json`, the export reads the existing file's `order` (if any) and computes the new `order`:

1. `kept` = ids from existing `order` that are still present in the new `profiles` set (preserves the user's custom sequence; drops renamed/deleted profiles).
2. `added` = ids in the new `profiles` set that are NOT in existing `order`, in **iTerm2 New Bookmarks traversal order** (the order profiles appear in iTerm2's profile list — preserved by `all_profiles` and captured before the `profiles` array is id-sorted for stable output).
3. New `order` = `kept + added`.

On first export (no existing file / no existing `order`): `order` = all profile ids in **iTerm2 New Bookmarks order**.

This guarantees: re-exporting preserves customization, removed profiles vanish from the order, and newly-added profiles land at the bottom in the same relative order iTerm2 shows them.

## 5. Export-script changes (`iterm2_to_ghostty.py`)

- `build_profiles_document(prefs, dynamic_dir, existing_order: list[str] | None = None)` — add an optional `existing_order` parameter. When provided, apply the §4.2 merge to produce the new `order`. The returned document gains an `"order"` key.
- `main` (in the `--export-profiles-json` dispatch): before serializing, read the existing output file (if it exists) and extract its `order` array; pass it to `build_profiles_document`. This keeps the merge logic in the pure function and the I/O in `main`.
- `--dry-run` still works (it just doesn't read or write the file; `existing_order` stays `None`, so dry-run always shows the alphabetical default — acceptable and documented).

## 6. New Raycast command: "Reorder iTerm Profiles"

### 6.1 Manifest

Add a second command to `raycast-extension/package.json`:

```json
{
  "name": "reorder",
  "title": "Reorder iTerm Profiles",
  "description": "Set a custom display order for exported iTerm profiles.",
  "mode": "view",
  "keywords": ["iterm", "ghostty", "order", "sort"]
}
```

Entry file: `src/reorder.tsx` (command `name` maps to `src/<name>.tsx`).

### 6.2 UI

- A flat `List` showing every profile (no `skip`), rendered in display-sort order (§4.1).
- Each `List.Item`:
  - `id={profile.id}` (stable — this is what lets Raycast keep the cursor on the moved item across re-renders).
  - `icon` by type (reuse `iconForType`), `title` = name, `subtitle` = command/working-directory (reuse `subtitleFor`), `accessories` = a position number `{ text: String(index + 1) }` so the user sees the rank.
  - `keywords` = name + tags (so search still works to find a profile among 78).
- Search bar retained — useful for finding a profile. Move actions operate on the **global** order (swap with the global predecessor/successor), not the filtered subset. (Documented: for predictable moves, clear search first; finding-then-clearing is the expected workflow.)

### 6.3 Actions & shortcuts

All shortcuts are Raycast command-scoped (active only while the Reorder command is open; never registered as OS-global hotkeys):

| Action | Shortcut | Behavior (on the selected profile's id in `order`) |
|---|---|---|
| Move Up | `⌥ ↑` | swap with the previous id in `order` |
| Move Down | `⌥ ↓` | swap with the next id in `order` |
| Move to Top | `⌥ ⌘ ↑` | move to position 0 |
| Move to Bottom | `⌥ ⌘ ↓` | move to the last position |
| Reset to Alphabetical | `⇧ ⌘ R` | rewrite `order` = all current ids sorted alphabetically by name |

At the top/bottom boundary, Move Up/Down are no-ops (the item stays; no error).

### 6.4 Selection retention

After every move, the order array changes and the list re-renders. Because each `List.Item` keeps a stable `id`, Raycast's cursor remains on the same profile and auto-scrolls it into view. The user can therefore hold `⌥` and press `↑` repeatedly to walk a profile up the list one slot per press.

### 6.5 Persistence (write-on-every-move)

Each move immediately persists: read `profiles.json` from disk, replace its `order` field with the new array (leaving `profiles`/`source`/etc. untouched), write it back. Rationale: tiny file (~78 ids), negligible I/O cost, and guarantees no loss if Raycast is closed mid-session. The `profiles` data is never modified by this command.

### 6.6 Empty / error states

- If `profiles.json` is missing/invalid: same error item as the main command, with a Refresh action (no move actions).
- If the file loads but has zero profiles: an empty-state item with the export-command hint.

## 7. Main command changes (`src/index.tsx`)

- `loadProfiles` (in `profiles.ts`) now also returns the document's `order` array, as a single object `{ profiles: Profile[]; order: string[] }` from one read (avoids double I/O). Both commands consume this shape.
- `index.tsx` renders profiles in display-sort order (§4.1) instead of the current id-sorted order. All other behavior (search via `keywords`, launch actions, Ghostty AppleScript) is unchanged.
- Error/empty states unchanged.

## 8. New module: `src/ordering.ts` (pure functions)

All order math is extracted into pure, unit-testable functions:

- `sortByOrder(profiles: Profile[], order: string[]): Profile[]` — applies §4.1.
- `moveUp(order: string[], id: string): string[]` — returns a new array with `id` swapped one slot earlier (no-op at boundary).
- `moveDown(order: string[], id: string): string[]` — symmetric.
- `moveToTop(order: string[], id: string): string[]`
- `moveToBottom(order: string[], id: string): string[]`
- `resetOrder(profiles: Profile[]): string[]` — returns ids sorted alphabetically by `name`.

All functions are pure (return new arrays; never mutate input) and have no I/O. `reorder.tsx` calls these and does the file read-modify-write.

## 9. Error handling

- **Export side:** if the existing `profiles.json` is unreadable/corrupt during the merge read, fall back to `existing_order = None` (treat as first export) and proceed — never block an export because of a stale/corrupt order file. Log nothing (CLI; the merge is best-effort).
- **Extension side:** `loadProfiles` already throws `ProfilesError` for missing/malformed files; the Reorder command reuses that path. A missing `order` field is NOT an error — it falls back to alphabetical.
- **Write side:** if the Reorder command's write fails (permissions, disk full), show a failure toast and keep the in-memory order so the user can retry; do not crash.

## 10. Testing

### Python (`tests/test_export_profiles_json.py`)

Extend with a `OrderMergeTests` class:

- First export (no existing order) → `order` = all new ids, alphabetical by **name**.
- Re-export preserves the existing order sequence for ids still present.
- Renamed/removed ids (in old `order`, gone from new profiles) are dropped from the new `order`.
- Newly-added ids (in new profiles, not in old `order`) are appended, alphabetical by **name**.
- Existing `order` containing ids that are NOT in the new profiles AND new profiles arriving together → both rules apply (drop the stale, append the new).
- `build_profiles_document` with `existing_order=None` matches the first-export behavior.

Existing tests stay green; the document now carries an `order` key (existing assertions that check `profiles`/`schema_version`/`source` are unaffected).

### TypeScript (`raycast-extension/src/__tests__/ordering.test.ts`)

- `sortByOrder`: empty order → alphabetical; order covers all → exact order; order covers some → ordered-ones first, rest alphabetical; duplicate ids in order → first occurrence wins; id in order but missing from profiles → skipped.
- `moveUp`/`moveDown`: middle swap; boundary no-op (returns equal array); `id` not in array → returns unchanged.
- `moveToTop`/`moveToBottom`: middle move; already-at-position no-op; missing id unchanged.
- `resetOrder`: returns ids sorted by `Profile.name`.

Pure functions, no React/filesystem in these tests.

## 11. MVP scope vs. later

**MVP (this implementation):**

- `order` field + export-script merge.
- Pure `ordering.ts` + tests.
- Reorder command (5 actions, selection retention, write-on-every-move).
- Main command renders in `order`.

**Later:**

- Undo/redo for moves.
- "Move to position N" (type a number in a Raycast Form).
- Cross-device sync (today: backed up by copying `profiles.json`).
- Bulk multi-select reorder.

## 12. Assumptions

- Profile ids are stable across re-exports for unchanged profiles (slug derived from name via `slugify_id`); renaming a profile in iTerm2 changes its id, so the old position is dropped and the renamed profile lands at the bottom — expected.
- Raycast tracks List selection by `List.Item.id`, so stable ids give free selection retention across re-renders. (Confirmed Raycast behavior.)
- Action shortcuts without modifiers do not fire while the List search bar is focused; therefore every move shortcut includes a modifier (`⌥`/`⌘`/`⇧`) — no plain-letter shortcuts.
