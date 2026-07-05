# iTerm2 Profiles → Ghostty via Raycast (Design Spec)

- **Date:** 2026-07-05
- **Status:** Approved (brainstorming complete), pending implementation plan
- **Goal:** Replace iTerm2's profile switcher with a Raycast extension that searches normalized iTerm2 profiles and opens them as Ghostty tabs/windows.

## 1. Context & Problem

The user is migrating from iTerm2 to Ghostty. Everything else (theme, fonts, window settings) is already configured in Ghostty. The remaining gap is **profiles**: iTerm2's searchable profile list used to open terminals that either SSH to a host, open a shell in a directory, or run a command.

Ghostty has **no profile system** and no profile-switcher UI. Its macOS CLI also cannot launch the terminal directly (only `+new-window` is available, and raw `ghostty` invocation is unsupported on macOS). However, Ghostty ships a complete **AppleScript** surface that can create tabs/windows with a working directory and a command.

The existing `iterm2_to_ghostty.py` in this repo converts a *single* iTerm2 profile into Ghostty's `config` file (colors, font, etc.). It does not handle the ~75 "launcher" profiles, and writing all of them into one `~/.config/ghostty/config` is not viable.

### Observed profile data

Inspecting the live iTerm2 plist (`com.googlecode.iterm2.plist`) shows **79 profiles**, none "plain":

| Kind | Count | Example |
|---|---|---|
| SSH (`ssh user@host`) | 25 | `Perficient PC Ubuntu` → `ssh jack@ubuntu1.jyang.eu.org` |
| Working-directory-only shell | 2 | `Go Bootcamp` → cwd `/Users/jack/workspaces/self/go-bootcamp` |
| Custom command + working dir | 52 | Most are effectively "open shell in directory" with a leftover `Command` field; `Custom Command = No` |

## 2. Architecture (chosen: Approach A)

Three layers, each owning one concern, connected by a JSON file as the stable contract.

```
iTerm2 plist (com.googlecode.iterm2.plist + DynamicProfiles)
        │
        │  Python export (extends iterm2_to_ghostty.py)
        ▼
profiles.json  (~/.config/ghostty/profiles.json)
        │
        │  TypeScript Raycast extension (runtime read)
        ▼
Raycast List  →  user picks profile + action
        │
        │  osascript invocation (generated per action)
        ▼
Ghostty surface (new tab / window / split) with cwd + command
```

**Why this split:** Python keeps doing what it already does well (plist parsing, including dynamic-profile merging and the quirk handling already implemented). TypeScript only renders a list and generates AppleScript. AppleScript is the *only* way to open a tab in an existing Ghostty window on macOS, so it is isolated behind a pure function that returns an `osascript` string.

**Repo layout (everything stays in this repo):**

```
iterm2-to-ghostty/
├── iterm2_to_ghostty.py          # existing; add --export-profiles-json mode
├── raycast-extension/            # new
│   ├── package.json
│   ├── src/
│   │   ├── index.tsx             # List + actions (root command)
│   │   ├── profiles.ts           # read + validate profiles.json
│   │   ├── applescript.ts        # pure osascript string generators
│   │   └── types.ts              # Profile type shared with JSON schema
│   └── ...
├── tests/
│   ├── test_export_profiles_json.py   # new
│   └── ...existing
└── docs/superpowers/specs/       # this document
```

Rejected alternatives:

- **B. Raycast reads the plist directly** — duplicates the profile normalization logic in TypeScript that Python already implements; couples the UI to raw plist quirks.
- **C. Python emits one script per profile** — inflexible; changing the default action requires re-export.

## 3. `profiles.json` schema (the contract)

Single object, written to `~/.config/ghostty/profiles.json`:

```json
{
  "schema_version": 1,
  "exported_at": "2026-07-05T12:00:00Z",
  "source": "com.googlecode.iterm2",
  "profiles": [
    {
      "id": "perficient-pc-ubuntu",
      "name": "Perficient PC Ubuntu",
      "type": "ssh",
      "working_directory": "/Users/jack",
      "command": "ssh jack@ubuntu1.jyang.eu.org",
      "tags": ["perficient", "pc", "ubuntu", "jack", "ubuntu1", "jyang", "cloud"],
      "skip": false,
      "raw": {
        "Guid": "FC192D07-5633-4AD2-8D54-B43A9D76ADFA",
        "Custom Command": "No",
        "Command": "ssh jack@ubuntu1.jyang.eu.org",
        "Working Directory": "/Users/jack",
        "Custom Directory": "No"
      }
    }
  ]
}
```

Field rules:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable slug derived from the name (lowercased, non-alphanumerics → `-`). Used as React key. |
| `name` | string | iTerm2 profile name verbatim. |
| `type` | `"ssh"` \| `"shell"` \| `"command"` | See type rules below. |
| `working_directory` | string \| null | Resolved cwd; null if none. |
| `command` | string \| null | What Ghostty should run. For `ssh`/`command` types this is set; for `shell` it is null. |
| `tags` | string[] | Lowercased, deduped search terms aggregated from multiple sources (see §4). Drives matching. |
| `skip` | boolean | `true` for the `Default` profile (excluded from the launcher). Editable. |
| `raw` | object | Selected raw plist fields, for audit/debugging. |

### Type detection rules

Applied in order to the merged iTerm2 bookmark dict:

1. If `command` (after `strip()`) starts with `ssh ` (case-insensitive) → **`ssh`**, set `command` to the full string.
2. Else if `Custom Command` ∈ {`Yes`, `Custom`} AND `command` is non-empty AND not a bare shell/login program → **`command`**, keep `command`.
3. Else → **`shell`**, set `command = null`. Use `working_directory` only.

The `Default` profile is force-marked `skip: true` regardless of type.

## 4. Tag extraction rules

`tags` is the union (lowercased, deduped, non-empty) of terms from these sources:

1. **Name tokens** — split on whitespace, camel/PascalCase boundaries, and punctuation. `BeCon Micro-Services China QA` → `becon, micro, services, china, qa`.
2. **Prefix bucket** — a single coarse tag from a prefix table (the only residue of the old "category" idea):
   - `BeCon*` → `becon`
   - `SCP*` → `scp`
   - `Perficient*` → `perficient`
   - `Azure*` → `cloud`
   - `Oracel*` / `Bosch*` / `AlwaysData*` / `Serv00*` → `cloud`
   - `Mi*` / `NAS*` / `Home*` / `iPhone*` / `Router*` → `home`
   - `AI*` → `ai`
   - otherwise → `misc`
3. **SSH host tokens** — for type `ssh`, parse `ssh [user@]host`. Add the user (if any), the hostname, and each dot-separated domain segment. `ssh jack@ubuntu1.jyang.eu.org` → `jack, ubuntu1, jyang, eu, org`.
4. **Working-directory path segments** — for a non-home path, add each non-trivial segment (length ≥ 3, not `Users`, not the username). `/Users/jack/workspaces/becon/beco.cloud.connectivity` → `workspaces, becon, beco, cloud, connectivity`.
5. **Command tokens** — for type `command`, add non-stopwords from the command string (length ≥ 3, excluding common shell tokens like `cd`, `sudo`).

Expected search behavior:

- `ubuntu` → all ubuntu hosts
- `becon qa` → BeCon profiles whose name/tags contain `qa`
- `nas` → the NAS profiles
- `jack` → every ssh profile that logs in as `jack`

## 5. Export script changes (`iterm2_to_ghostty.py`)

Add a new mode that does **not** write Ghostty's `config`; it writes `profiles.json` instead.

New CLI:

```
./iterm2_to_ghostty.py --export-profiles-json [PATH]
```

- Default output path: `~/.config/ghostty/profiles.json` (override with the positional `PATH` or `--output`).
- Reads the same inputs as today (main plist + dynamic profiles, merged by `Guid`), iterating **all** bookmarks rather than selecting one.
- Reuses existing helpers for loading/merging plist data; adds new helpers for type detection, tag extraction, and id slugification.
- `Default` is emitted with `skip: true` (still present, so the user can flip it if desired).
- Idempotent: running twice produces the same file (stable ordering by id).
- `--dry-run` prints the JSON to stdout instead of writing.
- Existing `--profile NAME` / config-writing behavior is unchanged.

## 6. Raycast extension

### 6.1 Entry point

A single Raycast command `Search iTerm Profiles` (keywords `iterm`, `ghostty`, `terminal`). Shows a `List`.

### 6.2 List rendering (flat, tag-driven)

- **No section grouping.** A flat list; matching is purely Raycast's native fuzzy search.
- Each `ListItem`:
  - `icon`: by type — ssh 🌐 / shell 🖥 / command ⚙️ (Raycast icon constants).
  - `title`: profile `name`.
  - `subtitle`: `command` if present, else `working_directory`, else `"(default shell)"`.
  - `accessories`: up to 3 tags, to hint at why the row is relevant.
  - `keywords`: `${name} ${tags.join(" ")} ${command ?? ""}` — **this is the matching surface.** Raycast fuzzy-matches the user query against this string.
  - Profiles with `skip: true` are filtered out.

### 6.3 Actions

The default action (Enter) is **Open in New Tab** (highest priority). The action panel (`⌘K`) exposes:

| Action | Priority | Notes |
|---|---|---|
| Open in New Tab | High (default) | New tab in frontmost window; falls back to new window if no window exists. |
| Open in New Window | Medium | Always `new window`. |
| Open as Split Pane (Right) | Low | New tab, then split right. **Not in MVP** (see §10); listed for completeness. |
| Copy Command | — | Copies `command` (or the would-be `cd` line for `shell`). |
| Reveal Working Directory in Finder | — | Only enabled when `working_directory` exists. |
| Refresh Profiles | — | Re-reads `profiles.json`. |

### 6.4 Empty / error states

- `profiles.json` missing → empty state with the exact command to run: `./iterm2_to_ghostty.py --export-profiles-json`.
- JSON present but malformed → toast `profiles.json is invalid: <reason>`, list hidden.
- Zero non-skipped profiles → empty state `No profiles exported yet`.

## 7. AppleScript launch layer

A pure function in `src/applescript.ts` takes a `Profile` and a target (`tab` | `window` | `split:right`) and returns an `osascript -e` invocation string. The extension runs it via `child_process.execFile`.

**New tab + ssh:**

```applescript
tell application "Ghostty"
  set cfg to new surface configuration
  set command of cfg to "ssh jack@ubuntu1.jyang.eu.org"
  if (count of windows) > 0 then
    set t to new tab with configuration cfg
  else
    set w to new window with configuration cfg
  end if
  activate
end tell
```

**New tab + shell in directory** (no `command` set → Ghostty opens the default shell there):

```applescript
tell application "Ghostty"
  set cfg to new surface configuration
  set initial working directory of cfg to "/Users/jack/workspaces/becon/beco.cloud.connectivity"
  if (count of windows) > 0 then
    set t to new tab with configuration cfg
  else
    set w to new window with configuration cfg
  end if
  activate
end tell
```

**New window:** replace the `if/else` block with `set w to new window with configuration cfg`.

**Split (low priority):** create the tab first, then `split t direction right with configuration cfg`.

Semantics notes:

- For `ssh`/`command` types, the `command` field *replaces* the shell, so exiting ssh closes the tab — matches iTerm2 behavior.
- For `shell` types, no `command` is set; Ghostty starts an interactive shell in the directory and the tab stays open.
- All strings interpolated into AppleScript are escaped (backslash and double-quote) to avoid injection from profile data.

## 8. Error handling

- **Export side:** missing plist → existing error path reused; a profile with neither command nor working directory is still emitted (as `shell` with nulls) and is launchable as a plain tab.
- **Extension side:** see §6.4 for JSON states. AppleScript failures (Ghostty not installed / not running) surface as a Raycast toast; the extension does not crash. Missing working directory is delegated to Ghostty (which typically falls back to `$HOME`).

## 9. Testing

### Python (`tests/test_export_profiles_json.py`)

Unit tests with hand-built bookmark dicts (no real plist needed):

- Type detection: `ssh` (with and without `Custom Command`), `command`, `shell` (including the `Command='cd'` + working-directory leftover case).
- `Default` profile → `skip: true`.
- Tag extraction: SSH host tokens, path segments, name tokenization, dedup, lowercase.
- `id` slug stability and uniqueness across similar names.
- `--dry-run` emits valid JSON to stdout without writing.
- Idempotency: two runs produce byte-identical output (stable ordering).

Existing tests for the config-writing mode remain green (the new mode is additive).

### TypeScript (`raycast-extension/`)

- `applescript.ts`: snapshot/string-equality tests — given a Profile and a target, the generated osascript string matches expected, including escaping of quotes/backslashes in command and path.
- Tag/profile loading: malformed JSON → throws a typed error the UI can render.
- The List component is covered by Raycast's own conventions; logic-heavy code is extracted into pure functions and unit-tested, not the JSX itself.

## 10. MVP scope vs. later

**MVP (this implementation):**

- `--export-profiles-json` export mode.
- Raycast command: flat List + tag-driven fuzzy search + actions Open in New Tab (default), Open in New Window, Copy Command, Reveal Directory, Refresh.

**Later:**

- Split-pane action.
- "Edit before run" form (tweak the command/cwd in a Raycast Form before launching).
- Watch the plist and auto-refresh `profiles.json`.
- Publish to the Raycast Store.

## 11. Open questions / assumptions

- Assumes Ghostty is installed at `/Applications/Ghostty.app` (AppleScript address `application "Ghostty"`). No fallback to other locations in MVP.
- Assumes `osascript` invocation latency is acceptable for a launcher (< 500 ms typical).
- The `Default` profile is skipped by default; the user can flip `skip: false` in the JSON.
- Tag extraction heuristics are intentionally over-inclusive; the user can edit the JSON to add/remove tags per profile.
