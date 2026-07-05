# Profile Custom Ordering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user define a custom display order for all exported profiles, editable from a new Raycast "Reorder" command, stored as a top-level `order` field in `profiles.json`, surviving re-export and appending new profiles at the bottom.

**Architecture:** The export script merges an existing `order` array across re-exports (Python). A pure `ordering.ts` module does all order math (sort + move transforms). `loadProfiles` returns `{ profiles, order }`. The new `reorder.tsx` command renders the list in order, offers opt+arrow move shortcuts with selection retention, and writes `order` back to `profiles.json` on every move.

**Tech Stack:** Python 3 stdlib (existing), TypeScript + React 19 + `@raycast/api`, `vitest`.

**Spec:** `docs/superpowers/specs/2026-07-05-profile-ordering-design.md`

---

## File Structure

**Python (modify):**
- `iterm2_to_ghostty.py` — `build_profiles_document` gains `existing_order` param + emits `order` key; `main`'s export dispatch reads the existing file's `order` and passes it.
- `tests/test_export_profiles_json.py` — add `OrderMergeTests`.

**TypeScript (new):**
- `raycast-extension/src/ordering.ts` — pure functions: `sortByOrder`, `moveUp`, `moveDown`, `moveToTop`, `moveToBottom`, `resetOrder`.
- `raycast-extension/src/__tests__/ordering.test.ts` — pure-logic tests.
- `raycast-extension/src/reorder.tsx` — the new Reorder command (entry for command `name: "reorder"`).

**TypeScript (modify):**
- `raycast-extension/src/types.ts` — add optional `order?: string[]` to `ProfilesDocument`.
- `raycast-extension/src/profiles.ts` — `loadProfiles` returns `{ profiles, order }`; add `saveProfilesOrder(path, order)`.
- `raycast-extension/src/index.tsx` — consume new shape, render via `sortByOrder`.
- `raycast-extension/src/__tests__/profiles.test.ts` — update assertions for new return shape.
- `raycast-extension/package.json` — add the `reorder` command.

---

## Task 1: Python — export-script order merge

**Files:**
- Modify: `iterm2_to_ghostty.py` (`build_profiles_document` at line 472; `main` export dispatch at line 1089)
- Test: `tests/test_export_profiles_json.py` (append `OrderMergeTests`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_export_profiles_json.py` (before the `if __name__ == "__main__":` block):

```python
class OrderMergeTests(unittest.TestCase):
    def _doc(self, names_and_types, existing_order=None):
        """Build a prefs dict of bookmarks named [(name, command), ...]."""
        prefs = {"New Bookmarks": [
            {"Name": n, "Command": c, "Custom Command": "No"} for n, c in names_and_types
        ]}
        return build_profiles_document(prefs, None, existing_order)

    def test_first_export_order_is_alphabetical_by_name(self):
        doc = self._doc([("Zeta", "ssh a@z"), ("Alpha", "ssh a@alpha"), ("Mi", "ssh a@mi")])
        # order lists ids; ids are slugified names; sorted by NAME not id.
        self.assertEqual(doc["order"], ["alpha", "mi", "zeta"])

    def test_reexport_preserves_existing_order_for_kept_ids(self):
        doc = self._doc(
            [("Alpha", "ssh a@alpha"), ("Mi", "ssh a@mi"), ("Zeta", "ssh a@z")],
            existing_order=["zeta", "mi", "alpha"],
        )
        self.assertEqual(doc["order"], ["zeta", "mi", "alpha"])

    def test_reexport_drops_stale_ids(self):
        # "ghost" is in existing_order but no longer a profile.
        doc = self._doc(
            [("Alpha", "ssh a@alpha"), ("Zeta", "ssh a@z")],
            existing_order=["zeta", "ghost", "alpha"],
        )
        self.assertEqual(doc["order"], ["zeta", "alpha"])

    def test_reexport_appends_new_ids_alphabetically_by_name(self):
        doc = self._doc(
            [("Alpha", "ssh a@alpha"), ("Beta", "ssh a@beta"), ("Zeta", "ssh a@z")],
            existing_order=["zeta", "alpha"],  # Beta is new
        )
        self.assertEqual(doc["order"], ["zeta", "alpha", "beta"])

    def test_combined_stale_and_new(self):
        doc = self._doc(
            [("Alpha", "ssh a@alpha"), ("Beta", "ssh a@beta"), ("Zeta", "ssh a@z")],
            existing_order=["zeta", "ghost", "alpha"],  # ghost stale; beta new
        )
        self.assertEqual(doc["order"], ["zeta", "alpha", "beta"])

    def test_existing_order_none_matches_first_export(self):
        doc_none = self._doc([("Zeta", "ssh a@z"), ("Alpha", "ssh a@alpha")], existing_order=None)
        doc_default = build_profiles_document(
            {"New Bookmarks": [
                {"Name": "Zeta", "Command": "ssh a@z", "Custom Command": "No"},
                {"Name": "Alpha", "Command": "ssh a@alpha", "Custom Command": "No"},
            ]},
            None,
        )
        self.assertEqual(doc_none["order"], doc_default["order"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_export_profiles_json.OrderMergeTests -v`
Expected: FAIL — `TypeError: build_profiles_document() takes ... positional arguments` (it doesn't accept `existing_order` yet), and `doc["order"]` is a KeyError.

- [ ] **Step 3: Modify `build_profiles_document`**

At line 472 of `iterm2_to_ghostty.py`, replace the function signature and body so it accepts `existing_order` and emits an `order` key:

```python
def build_profiles_document(
    prefs: dict[str, Any],
    dynamic_dir: Path | None,
    existing_order: list[str] | None = None,
) -> dict[str, Any]:
    """Build the full profiles.json document from iTerm2 preferences (spec §3, §4.2)."""
    bookmarks = all_profiles(prefs, dynamic_dir)
    normalized = [normalize_profile(b) for b in bookmarks if isinstance(b, dict)]
    # Keep skipped profiles OUT of the document entirely (cleaner for the UI).
    normalized = [p for p in normalized if not p.get("skip")]
    normalized.sort(key=lambda p: p["id"])

    name_by_id = {p["id"]: p["name"] for p in normalized}
    if existing_order:
        existing_set = set(existing_order)
        kept = [i for i in existing_order if i in name_by_id]  # drop stale/renamed ids
        added = sorted(
            (i for i in name_by_id if i not in existing_set),
            key=lambda i: name_by_id[i],
        )
        order = kept + added
    else:
        order = sorted(name_by_id.keys(), key=lambda i: name_by_id[i])

    return {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": ITERM_DOMAIN,
        "order": order,
        "profiles": normalized,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_export_profiles_json.OrderMergeTests -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Wire `main` to read and pass the existing order**

At line 1089 in `main`, replace the dispatch block so it reads the existing `order` before building the document. Replace the line:

```python
        document = build_profiles_document(prefs, args.dynamic_profiles_dir)
```

with:

```python
        existing_order: list[str] | None = None
        if not args.dry_run and args.export_profiles_json.exists():
            try:
                with open(args.export_profiles_json, "rb") as fh:
                    old = json.load(fh)
                if isinstance(old.get("order"), list):
                    existing_order = [str(x) for x in old["order"]]
            except (OSError, ValueError):
                existing_order = None
        document = build_profiles_document(
            prefs, args.dynamic_profiles_dir, existing_order
        )
```

(Dry-run deliberately does not merge: with no file read, `existing_order` stays `None` and dry-run shows the alphabetical default — documented in spec §5.)

- [ ] **Step 6: Run the full Python suite + smoke-test**

Run: `python3 -m unittest discover -s tests -v` — all tests PASS (existing + 6 new).
Run: `python3 -m py_compile iterm2_to_ghostty.py && echo OK` — prints `OK`.

Smoke-test the merge end-to-end:
```bash
./iterm2_to_ghostty.py --export-profiles-json   # first export → alphabetical order
python3 -c "import json; d=json.load(open('$HOME/.config/ghostty/profiles.json')); print('order len', len(d['order']), 'first', d['order'][:3])"
```
Expected: `order len 78` (or current count), first few ids in alphabetical-by-name order.

Re-run the export; confirm the `order` is unchanged on the second run (idempotent for a stable profile set):
```bash
./iterm2_to_ghostty.py --export-profiles-json
python3 -c "import json; print(json.load(open('$HOME/.config/ghostty/profiles.json'))['order'][:3])"
```
Expected: same first-three ids as before (the merge preserved the existing order).

- [ ] **Step 7: Commit**

```bash
git add iterm2_to_ghostty.py tests/test_export_profiles_json.py
git commit -m "Merge existing order across exports; emit profiles.json order field"
```

---

## Task 2: TypeScript — `ordering.ts` pure functions

**Files:**
- Create: `raycast-extension/src/ordering.ts`
- Test: `raycast-extension/src/__tests__/ordering.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `raycast-extension/src/__tests__/ordering.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import {
  sortByOrder,
  moveUp,
  moveDown,
  moveToTop,
  moveToBottom,
  resetOrder,
} from "../ordering";
import type { Profile } from "../types";

function profile(id: string, name: string = id): Profile {
  return {
    id,
    name,
    type: "shell",
    working_directory: null,
    command: null,
    tags: [],
    skip: false,
    raw: {},
  };
}

const P = [profile("a", "Alpha"), profile("b", "Beta"), profile("c", "Charlie")];

describe("sortByOrder", () => {
  it("empty order falls back to alphabetical by name", () => {
    expect(sortByOrder(P, []).map((p) => p.id)).toEqual(["a", "b", "c"]);
  });

  it("order covers all -> exact order", () => {
    expect(sortByOrder(P, ["c", "a", "b"]).map((p) => p.id)).toEqual(["c", "a", "b"]);
  });

  it("order covers some -> ordered first, rest alphabetical", () => {
    expect(sortByOrder(P, ["c"]).map((p) => p.id)).toEqual(["c", "a", "b"]);
  });

  it("duplicate ids in order -> first occurrence wins", () => {
    expect(sortByOrder(P, ["c", "c", "a"]).map((p) => p.id)).toEqual(["c", "a", "b"]);
  });

  it("id in order but missing from profiles -> skipped", () => {
    expect(sortByOrder(P, ["ghost", "b"]).map((p) => p.id)).toEqual(["b", "a", "c"]);
  });
});

describe("moveUp / moveDown", () => {
  it("moveUp swaps with predecessor", () => {
    expect(moveUp(["a", "b", "c"], "b")).toEqual(["b", "a", "c"]);
  });
  it("moveUp at top is a no-op", () => {
    expect(moveUp(["a", "b", "c"], "a")).toEqual(["a", "b", "c"]);
  });
  it("moveDown swaps with successor", () => {
    expect(moveDown(["a", "b", "c"], "b")).toEqual(["a", "c", "b"]);
  });
  it("moveDown at bottom is a no-op", () => {
    expect(moveDown(["a", "b", "c"], "c")).toEqual(["a", "b", "c"]);
  });
  it("moveUp/Down with missing id -> unchanged", () => {
    expect(moveUp(["a", "b"], "ghost")).toEqual(["a", "b"]);
    expect(moveDown(["a", "b"], "ghost")).toEqual(["a", "b"]);
  });
});

describe("moveToTop / moveToBottom", () => {
  it("moveToTop from middle", () => {
    expect(moveToTop(["a", "b", "c"], "c")).toEqual(["c", "a", "b"]);
  });
  it("moveToTop already first -> unchanged", () => {
    expect(moveToTop(["a", "b"], "a")).toEqual(["a", "b"]);
  });
  it("moveToBottom from middle", () => {
    expect(moveToBottom(["a", "b", "c"], "a")).toEqual(["b", "c", "a"]);
  });
  it("moveToBottom already last -> unchanged", () => {
    expect(moveToBottom(["a", "b"], "b")).toEqual(["a", "b"]);
  });
  it("missing id -> unchanged", () => {
    expect(moveToTop(["a"], "ghost")).toEqual(["a"]);
    expect(moveToBottom(["a"], "ghost")).toEqual(["a"]);
  });
});

describe("resetOrder", () => {
  it("returns ids sorted alphabetically by name", () => {
    const ps = [profile("z", "Zeta"), profile("a", "Alpha"), profile("m", "Mi")];
    expect(resetOrder(ps)).toEqual(["a", "m", "z"]);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `raycast-extension/`): `npm test`
Expected: FAIL — `Cannot find module '../ordering'`.

- [ ] **Step 3: Write `raycast-extension/src/ordering.ts`**

```typescript
import type { Profile } from "./types";

/** Render profiles in display-sort order (spec §4.1):
 *  ids in `order` first (in array order, first occurrence wins on dup),
 *  then remaining profiles alphabetically by name. */
export function sortByOrder(profiles: Profile[], order: string[]): Profile[] {
  const byId = new Map(profiles.map((p) => [p.id, p]));
  const seen = new Set<string>();
  const ordered: Profile[] = [];
  for (const id of order) {
    if (seen.has(id)) continue;
    const p = byId.get(id);
    if (p) {
      ordered.push(p);
      seen.add(id);
    }
  }
  const rest = profiles.filter((p) => !seen.has(p.id));
  rest.sort((a, b) => a.name.localeCompare(b.name));
  return [...ordered, ...rest];
}

function swap(order: string[], id: string, delta: -1 | 1): string[] {
  const i = order.indexOf(id);
  if (i < 0) return order;
  const j = i + delta;
  if (j < 0 || j >= order.length) return order;
  const next = order.slice();
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

export function moveUp(order: string[], id: string): string[] {
  return swap(order, id, -1);
}

export function moveDown(order: string[], id: string): string[] {
  return swap(order, id, 1);
}

export function moveToTop(order: string[], id: string): string[] {
  const i = order.indexOf(id);
  if (i <= 0) return order;
  const next = order.slice();
  next.splice(i, 1);
  next.unshift(id);
  return next;
}

export function moveToBottom(order: string[], id: string): string[] {
  const i = order.indexOf(id);
  if (i < 0 || i === order.length - 1) return order;
  const next = order.slice();
  next.splice(i, 1);
  next.push(id);
  return next;
}

/** Return ids sorted alphabetically by profile name. */
export function resetOrder(profiles: Profile[]): string[] {
  return profiles.slice().sort((a, b) => a.name.localeCompare(b.name)).map((p) => p.id);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS (ordering tests + existing applescript/profiles tests).

- [ ] **Step 5: Type-check + build**

Run: `npx tsc --noEmit` — clean.
Run: `npm run build` — exit 0.

- [ ] **Step 6: Commit**

```bash
git add raycast-extension/src/ordering.ts raycast-extension/src/__tests__/ordering.test.ts
git commit -m "Add pure ordering functions (sort + move transforms)"
```

---

## Task 3: TypeScript — `loadProfiles` returns `{ profiles, order }`; main command renders by order

**Files:**
- Modify: `raycast-extension/src/types.ts`
- Modify: `raycast-extension/src/profiles.ts`
- Modify: `raycast-extension/src/__tests__/profiles.test.ts`
- Modify: `raycast-extension/src/index.tsx`

- [ ] **Step 1: Update tests first (they encode the new contract)**

In `raycast-extension/src/__tests__/profiles.test.ts`, the valid-JSON test currently asserts on the return value directly. Update it to destructure `{ profiles, order }` and assert both. Replace the body of the `"returns the profiles array when the JSON is valid"` test:

```typescript
  it("returns profiles and order when the JSON is valid", () => {
    const path = join(tmp, "profiles.json");
    writeFileSync(
      path,
      JSON.stringify({
        schema_version: 1,
        exported_at: "2026-07-05T00:00:00Z",
        source: "com.googlecode.iterm2",
        order: ["nas", "other"],
        profiles: [
          {
            id: "nas",
            name: "NAS",
            type: "ssh",
            working_directory: null,
            command: "ssh admin@nas.local",
            tags: ["nas", "home"],
            skip: false,
            raw: {},
          },
        ],
      })
    );
    const { profiles, order } = loadProfiles(path);
    expect(profiles).toHaveLength(1);
    expect(profiles[0].name).toBe("NAS");
    expect(order).toEqual(["nas", "other"]);
  });

  it("returns empty order when the field is absent (backward compat)", () => {
    const path = join(tmp, "legacy.json");
    writeFileSync(
      path,
      JSON.stringify({
        schema_version: 1,
        exported_at: "2026-07-05T00:00:00Z",
        source: "com.googlecode.iterm2",
        profiles: [],
      })
    );
    const { order } = loadProfiles(path);
    expect(order).toEqual([]);
  });
```

(The other 3 tests — missing file, malformed JSON, absent schema_version — still assert `toThrow(ProfilesError)`; they don't need changes since they call `loadProfiles(path)` and expect a throw before any destructuring.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — the valid-JSON test fails because `loadProfiles` returns an array (`.profiles` is undefined) and `.order` is undefined.

- [ ] **Step 3: Update `raycast-extension/src/types.ts`**

Add optional `order` to `ProfilesDocument`:

```typescript
export interface ProfilesDocument {
  schema_version: number;
  exported_at: string;
  source: string;
  order?: string[];
  profiles: Profile[];
}
```

- [ ] **Step 4: Update `raycast-extension/src/profiles.ts`**

Change `loadProfiles` to return `{ profiles, order }`. Edit the signature, the return statement, and add a `LoadedProfiles` type. Replace the function (currently lines ~16–46) with:

```typescript
export interface LoadedProfiles {
  profiles: Profile[];
  order: string[];
}

/** Load and validate profiles.json. Throws ProfilesError on any problem. */
export function loadProfiles(path: string = DEFAULT_PROFILES_PATH): LoadedProfiles {
  let raw: string;
  try {
    raw = readFileSync(path, "utf-8");
  } catch (err) {
    throw new ProfilesError(
      `Could not read ${path}. Run \`./iterm2_to_ghostty.py --export-profiles-json\` first. (${
        (err as NodeJS.ErrnoException).message
      })`
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new ProfilesError(
      `profiles.json is invalid JSON: ${(err as Error).message}`
    );
  }

  const doc = parsed as Partial<ProfilesDocument>;
  if (!doc || typeof doc !== "object" || doc.schema_version !== 1) {
    throw new ProfilesError(
      "profiles.json is missing schema_version: 1. Re-run the export script."
    );
  }
  if (!Array.isArray(doc.profiles)) {
    throw new ProfilesError("profiles.json has no profiles array.");
  }
  const order = Array.isArray(doc.order) ? doc.order.filter((x) => typeof x === "string") : [];
  return {
    profiles: doc.profiles.filter((p) => p && !p.skip) as Profile[],
    order: order as string[],
  };
}
```

- [ ] **Step 5: Update `raycast-extension/src/index.tsx`**

The main command must consume the new shape and render in `order`. Make three edits:

(a) Add imports at the top (after the existing `./profiles`, `./applescript`, `./types` imports):

```tsx
import { sortByOrder } from "./ordering";
```

(b) Change the `useState` lazy initializer and `refresh` so they store `{ profiles, order, error }`. Replace the current `useState` + `refresh` block:

```tsx
  const [{ profiles, order, error }, setState] = useState(() => {
    try {
      const loaded = loadProfiles();
      return {
        profiles: loaded.profiles,
        order: loaded.order,
        error: null as string | null,
      };
    } catch (err) {
      return {
        profiles: [] as Profile[],
        order: [] as string[],
        error: err instanceof ProfilesError ? err.message : (err as Error).message,
      };
    }
  });

  const refresh = useCallback(() => {
    try {
      const loaded = loadProfiles();
      setState({ profiles: loaded.profiles, order: loaded.order, error: null });
    } catch (err) {
      setState({
        profiles: [],
        order: [],
        error: err instanceof ProfilesError ? err.message : (err as Error).message,
      });
    }
  }, []);
```

(c) Sort the rendered list. In the main `return` (the populated `List`), wrap the map source. Find:

```tsx
      {profiles.map((profile) => (
```

and replace with:

```tsx
      {sortByOrder(profiles, order).map((profile) => (
```

Leave every `List.Item` prop unchanged.

- [ ] **Step 6: Run tests + type-check + build**

Run: `npm test` — PASS (all tests, incl. the two updated/added profiles tests and the ordering tests).
Run: `npx tsc --noEmit` — clean.
Run: `npm run build` — exit 0.

- [ ] **Step 7: Commit**

```bash
git add raycast-extension/src/types.ts raycast-extension/src/profiles.ts raycast-extension/src/index.tsx raycast-extension/src/__tests__/profiles.test.ts
git commit -m "loadProfiles returns {profiles, order}; main list renders in custom order"
```

---

## Task 4: TypeScript — Reorder command

**Files:**
- Modify: `raycast-extension/package.json` (add `reorder` command)
- Modify: `raycast-extension/src/profiles.ts` (add `saveProfilesOrder`)
- Create: `raycast-extension/src/reorder.tsx`

- [ ] **Step 1: Add `saveProfilesOrder` to `raycast-extension/src/profiles.ts`**

Add `writeFileSync` to the existing `node:fs` import at the top:

```typescript
import { readFileSync, writeFileSync } from "node:fs";
```

Append at the end of the file:

```typescript
/**
 * Persist a new `order` array into profiles.json via read-modify-write.
 * Preserves every other field (profiles, source, etc.). Throws on I/O or parse error.
 */
export function saveProfilesOrder(path: string = DEFAULT_PROFILES_PATH, order: string[]): void {
  const raw = readFileSync(path, "utf-8");
  const doc = JSON.parse(raw) as Record<string, unknown>;
  doc.order = order;
  writeFileSync(path, JSON.stringify(doc, null, 2) + "\n", "utf-8");
}
```

- [ ] **Step 2: Add the `reorder` command to `raycast-extension/package.json`**

Add a second entry to the `commands` array (after the existing `index` command):

```json
    , {
      "name": "reorder",
      "title": "Reorder iTerm Profiles",
      "description": "Set a custom display order for exported iTerm profiles.",
      "mode": "view",
      "keywords": ["iterm", "ghostty", "order", "sort"]
    }
```

(Command `name: "reorder"` maps to entry file `src/reorder.tsx`.)

- [ ] **Step 3: Write `raycast-extension/src/reorder.tsx`**

The actions are defined inline inside the map callback so they close over `order`, `profile.id`, `profiles`, and `apply` — no module-scope state, no helper function, no prop-drilling.

```tsx
import React, { useState, useCallback } from "react";
import {
  Action,
  ActionPanel,
  Icon,
  Keyboard,
  List,
  showToast,
  Toast,
} from "@raycast/api";
import {
  loadProfiles,
  saveProfilesOrder,
  DEFAULT_PROFILES_PATH,
  ProfilesError,
} from "./profiles";
import {
  sortByOrder,
  moveUp,
  moveDown,
  moveToTop,
  moveToBottom,
  resetOrder,
} from "./ordering";
import type { Profile } from "./types";
import { iconForType, subtitleFor } from "./index";

export default function Command() {
  const [{ profiles, order, error }, setState] = useState(() => {
    try {
      const loaded = loadProfiles();
      return {
        profiles: loaded.profiles,
        order: loaded.order,
        error: null as string | null,
      };
    } catch (err) {
      return {
        profiles: [] as Profile[],
        order: [] as string[],
        error: err instanceof ProfilesError ? err.message : (err as Error).message,
      };
    }
  });

  const apply = useCallback((nextOrder: string[]) => {
    setState((s) => ({ ...s, order: nextOrder }));
    try {
      saveProfilesOrder(DEFAULT_PROFILES_PATH, nextOrder);
    } catch (err) {
      showToast({
        style: Toast.Style.Failure,
        title: "Could not save order",
        message: (err as Error).message,
      });
    }
  }, []);

  if (error) {
    return (
      <List>
        <List.Item icon={Icon.ExclamationMark} title="No profiles loaded" subtitle={error} />
      </List>
    );
  }

  const sorted = sortByOrder(profiles, order);

  return (
    <List
      navigationTitle="Reorder iTerm Profiles"
      searchBarPlaceholder="Find a profile to move (clear search before bulk moves)"
    >
      {sorted.map((profile, index) => (
        <List.Item
          key={profile.id}
          id={profile.id}
          icon={iconForType(profile.type)}
          title={profile.name}
          subtitle={subtitleFor(profile)}
          accessories={[{ text: String(index + 1) }]}
          keywords={[profile.name, ...profile.tags]}
          actions={
            <ActionPanel>
              <Action
                title="Move Up"
                icon={Icon.ArrowUp}
                shortcut={{ modifiers: ["opt"], key: Keyboard.KeyArrowUp }}
                onAction={() => apply(moveUp(order, profile.id))}
              />
              <Action
                title="Move Down"
                icon={Icon.ArrowDown}
                shortcut={{ modifiers: ["opt"], key: Keyboard.KeyArrowDown }}
                onAction={() => apply(moveDown(order, profile.id))}
              />
              <Action
                title="Move to Top"
                icon={Icon.ChevronUp}
                shortcut={{ modifiers: ["opt", "cmd"], key: Keyboard.KeyArrowUp }}
                onAction={() => apply(moveToTop(order, profile.id))}
              />
              <Action
                title="Move to Bottom"
                icon={Icon.ChevronDown}
                shortcut={{ modifiers: ["opt", "cmd"], key: Keyboard.KeyArrowDown }}
                onAction={() => apply(moveToBottom(order, profile.id))}
              />
              <Action
                title="Reset to Alphabetical"
                icon={Icon.ArrowClockwise}
                shortcut={{ modifiers: ["cmd", "shift"], key: "r" }}
                onAction={() => apply(resetOrder(profiles))}
              />
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}
```

`Keyboard.KeyArrowUp` / `Keyboard.KeyArrowDown` are the Raycast constants for the arrow keys. `iconForType` and `subtitleFor` are imported from `./index` (exported in Step 4).

- [ ] **Step 4: Export `iconForType` / `subtitleFor` from `src/index.tsx`**

In `src/index.tsx`, change `function iconForType` → `export function iconForType` and `function subtitleFor` → `export function subtitleFor` so `reorder.tsx` can import them (no duplication). No other change to that file.

- [ ] **Step 5: Type-check + tests + build**

Run: `npx tsc --noEmit` — clean.
Run: `npm test` — PASS (no new tests for `reorder.tsx` UI; existing tests must stay green).
Run: `npm run build` — exit 0.

- [ ] **Step 6: Commit**

```bash
git add raycast-extension/package.json raycast-extension/src/profiles.ts raycast-extension/src/reorder.tsx raycast-extension/src/index.tsx
git commit -m "Add Reorder command with opt+arrow move shortcuts and persistence"
```

---

## Task 5: End-to-end verification

**Files:** none (verification; some steps need the user)

- [ ] **Step 1: Re-export with order**

Run: `./iterm2_to_ghostty.py --export-profiles-json`
Expected: writes profiles.json now containing a top-level `order` array.
Confirm: `python3 -c "import json; d=json.load(open('$HOME/.config/ghostty/profiles.json')); print('order' in d, len(d['order']))"` → `True <N>`.

- [ ] **Step 2: Full automated suite**

```bash
python3 -m unittest discover -s tests
python3 -m py_compile iterm2_to_ghostty.py
cd raycast-extension && npm test && npx tsc --noEmit && npm run build
```
Expected: all green.

- [ ] **Step 3: GUI — main command reflects order (USER)**

Run `npm run dev` (from `raycast-extension/`). In Raycast:
- Open "Search iTerm Profiles". The list should now be alphabetical by name (no custom order set yet).
- Open "Reorder iTerm Profiles" (search "reorder"). Confirm all profiles show with position numbers (1..N).

- [ ] **Step 4: GUI — move + selection retention (USER)**

In "Reorder iTerm Profiles":
- Select any profile, press `⌥↑` once. It should swap with the one above; **the same profile stays selected**.
- Hold `⌥` and press `↑` several times. The profile walks up the list one slot per press, selection following.
- Press `⌥⌘↑` (Move to Top) — profile jumps to position 1, still selected.
- Press `⇧⌘R` (Reset) — list reverts to alphabetical.

- [ ] **Step 5: GUI — persistence across reopen (USER)**

In "Reorder iTerm Profiles", move 2–3 profiles, then close Raycast. Reopen "Search iTerm Profiles" — the moved profiles must appear in their new positions (proves the write-back worked).

- [ ] **Step 6: GUI — re-export preserves custom order (USER)**

Run `./iterm2_to_ghostty.py --export-profiles-json` again. Reopen "Search iTerm Profiles" — your custom order must be unchanged (the merge preserved it).

- [ ] **Step 7: Commit if any verification fixes were made**

If small fixes were needed during verification, commit them; otherwise this task produces no commit.

---

## Self-Review Notes (applied during authoring)

- **Spec coverage:** §3 schema → Task 1 (`order` key) + Task 3 (`order?` type). §4.1 sort → `sortByOrder` (Task 2) used in Task 3 (main) + Task 4 (reorder). §4.2 merge → Task 1. §5 export changes → Task 1. §6 Reorder command → Task 4. §7 main command changes → Task 3. §8 ordering.ts → Task 2. §9 error handling → Task 4 (save failure toast) + Task 3 (ProfilesError reused). §10 tests → Tasks 1 (Python) + 2 (TS). §11 MVP scope matches (no undo, no "move to N").
- **Type consistency:** `LoadedProfiles = { profiles, order }` introduced in Task 3 is consumed identically by `index.tsx` (Task 3) and `reorder.tsx` (Task 4). `ordering.ts` function signatures match between Task 2 (def + tests) and Task 4 (reorder.tsx call sites). `Keyboard.KeyArrowUp`/`KeyArrowDown` are valid Raycast constants.
- **No placeholders:** every code step contains runnable code. `reorder.tsx` uses inline closure-based actions (no module-scope state, no ambiguity); `iconForType`/`subtitleFor` are shared via `export` from `index.tsx`.
- **Sequencing:** Task 1 (Python) is independent. Tasks 2→3→4 build on each other but each leaves the build green (Task 3 updates all `loadProfiles` consumers in one task; Task 4 only adds new code + two `export` keyword edits).
