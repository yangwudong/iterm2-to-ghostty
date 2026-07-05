# Sync Entry — Design Spec

- **Date:** 2026-07-05
- **Status:** Approved (brainstorming complete); small feature — to be implemented directly with TDD (no separate plan)
- **Parent:** `2026-07-05-profile-ordering-design.md`
- **Goal:** Let the user trigger an iTerm2 → profiles.json re-export from directly within the "Search Ghostty Profiles" list, by selecting a pinned synthetic entry that opens Ghostty and runs the export script there.

## 1. Why

After the initial migration the user still occasionally adds/edits profiles in iTerm2 and must re-run `./iterm2_to_ghostty.py --export-profiles-json`. Today that requires opening a terminal. The user wants the trigger living **inside the profiles list** (discoverable, single mental model) rather than as a separate Raycast command. Running inside Ghostty (rather than directly in Raycast) sidesteps the GUI-app PATH/python problem entirely — Ghostty opens a real login shell.

## 2. Design

### 2.1 Preference (one-time setup)

A command-level preference on the `index` (Search) command:
- `name: "scriptPath"`, `type: "file"`, `required: false`, `title: "iterm2_to_ghostty.py"`, `description: "Path to the export script. Used by the *** Sync Profiles *** entry."`
- Accessed via `getPreferenceValues<Preferences.Index>()` → `scriptPath: string` (empty string when unset).
- Optional so that Search itself works without configuration; only the Sync action requires it.

### 2.2 Synthetic entry (UI-only — never written to profiles.json)

Injected ONLY in the Search command's `List`. NOT in the Reorder command, NOT emitted by the Python export.

- `id: "__sync__"`, `title: "*** Sync Profiles ***"`, `subtitle: "Re-export from iTerm2"`, icon `Icon.ArrowClockwise`.
- **Always pinned last**, appended after the filtered real profiles. Immune to the custom `order`.
- **Search visibility**: shown when the query is empty OR the query matches the entry's search hay (`"sync profiles export iterm ghostty"`). Computed by running `filterProfiles` on a pseudo-profile, so the same token-AND matching applies. Hidden for queries like "ubuntu".

### 2.3 Action (Enter = "Sync Now")

Opens Ghostty (new tab; falls back to new window if none) and runs the export inside a login shell, with the surface kept open so the user sees the result:

```
/bin/zsh -lc "python3 '<scriptPath>' --export-profiles-json"
```

- The Ghostty `surface configuration` sets `command` to that shell invocation and `wait after command` to `true` — so the tab does NOT auto-close after the command exits; the user reads "Wrote N profiles to ..." and closes it manually.
- `/bin/zsh -lc` ensures the user's full login PATH is used, so `python3` resolves the same way it does in their terminal.
- `<scriptPath>` single-quoted to tolerate spaces in the path; the whole shell command is run through `escapeAppleString` before being placed in the AppleScript double-quoted literal.
- If `scriptPath` is empty: show a `Toast.Failure` "Set the script path in command preferences" and (via the action) call `openCommandPreferences()` so the user can set it.

### 2.4 After sync

The user closes the Ghostty tab, returns to the Raycast Search command, and hits **Refresh** — the newly-exported `profiles` and merged `order` load.

## 3. New code

- `buildSyncAppleScript(scriptPath: string, target: LaunchTarget): string` in `src/applescript.ts` — pure; generates the `command` + `wait after command` + tab/window-fallback AppleScript. Unit-tested (string-equality): contains the escaped shell command, `wait after command of cfg to true`, the tab/window fallback; correctly escapes quotes in `scriptPath`.
- `index.tsx` changes:
  - Import `getPreferenceValues`, `openCommandPreferences`.
  - Read `scriptPath` once.
  - Build the filtered real-profile list as today, then conditionally append the `__sync__` `List.Item` (visibility via `filterProfiles` on the pseudo-profile).
  - The sync `List.Item`'s `ActionPanel`: `Sync Now` (default) → if `scriptPath`, `execFile("osascript", ["-e", buildSyncAppleScript(scriptPath, "tab")])` + `Toast.Success`; else `Toast.Failure` + `openCommandPreferences()`.

## 4. Out of scope

- A "Copy Sync Command" secondary action (can add later if wanted).
- Auto-refreshing the Search list after sync (manual Refresh is fine for now).
- Running the export directly inside Raycast (rejected — GUI PATH issues).
- Showing the sync entry in the Reorder command (it isn't a real profile).

## 5. Assumptions

- The user's default login shell is zsh (true on this Mac; env reports `Shell: zsh`). `/bin/zsh -lc` sources their profiles and finds `python3`.
- The Raycast `file` preference returns an absolute path, so the constructed shell command is location-independent.
- `wait after command` is a supported Ghostty `surface configuration` field (per the Ghostty AppleScript docs).

## 6. Testing

- `applescript.test.ts`: add a `buildSyncAppleScript` suite — verifies the generated osascript contains the escaped shell command with the script path, `wait after command of cfg to true`, and the tab/window fallback; verifies a script path containing a double-quote is correctly escaped.
- No unit test for the `index.tsx` injection (UI); verified manually in Raycast.
