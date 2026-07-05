# iTerm2 Profiles → Ghostty via Raycast — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace iTerm2's profile switcher with a Raycast extension that searches normalized iTerm2 profiles and opens them as Ghostty tabs/windows via AppleScript.

**Architecture:** A Python export mode (added to the existing `iterm2_to_ghostty.py`) reads the iTerm2 plist and writes `~/.config/ghostty/profiles.json`. A TypeScript Raycast extension reads that JSON, shows a flat tag-driven searchable `List`, and on selection runs an `osascript` that drives Ghostty's AppleScript surface to open a tab/window with the right working directory and command.

**Tech Stack:** Python 3 (stdlib only — `plistlib`, `argparse`, `json`, `re`, `unittest`), TypeScript + React + `@raycast/api`, `vitest` for TS unit tests, `osascript` for Ghostty control.

**Spec:** `docs/superpowers/specs/2026-07-05-iterm-ghostty-raycast-design.md`

---

## File Structure

**Python (modify existing):**
- `iterm2_to_ghostty.py` — add helper functions (`slugify_id`, `detect_type`, tag extractors, `normalize_profile`, `export_profiles_json`) and a new `--export-profiles-json` CLI mode. New helpers go after `select_profile()` (around line 273), the CLI flag in `parse_args()`, and the dispatch in `main()`.
- `tests/test_export_profiles_json.py` — new; pure-function unit tests, `unittest`, matches `tests/test_conversion.py` style.

**TypeScript (new, under `raycast-extension/`):**
- `raycast-extension/package.json` — Raycast manifest + deps. Command `name: "index"` → entry `src/index.tsx`.
- `raycast-extension/tsconfig.json` — standard Raycast TS config.
- `raycast-extension/vitest.config.ts` — minimal.
- `raycast-extension/assets/icon.png` — 512×512 icon (generated).
- `raycast-extension/src/types.ts` — `Profile` interface mirroring the JSON schema.
- `raycast-extension/src/profiles.ts` — read + validate `profiles.json`.
- `raycast-extension/src/applescript.ts` — pure `osascript` string generators (one per target: tab/window/split).
- `raycast-extension/src/index.tsx` — Raycast `List` + `ActionPanel`.
- `raycast-extension/src/__tests__/applescript.test.ts` — string-equality tests.
- `raycast-extension/src/__tests__/profiles.test.ts` — JSON validation tests.

---

## Task 1: `id` slugification helper

**Files:**
- Modify: `iterm2_to_ghostty.py` (insert after line 272, the end of `select_profile`)
- Test: `tests/test_export_profiles_json.py` (new file)

- [ ] **Step 1: Write the failing test**

Create `tests/test_export_profiles_json.py`:

```python
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iterm2_to_ghostty import slugify_id


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_replaces_non_alnum_with_dash(self):
        self.assertEqual(slugify_id("Perficient PC Ubuntu"), "perficient-pc-ubuntu")

    def test_collapses_repeated_separators(self):
        self.assertEqual(slugify_id("BeCon Micro-Services"), "becon-micro-services")
        self.assertEqual(slugify_id("NAS2 / Server"), "nas2-server")

    def test_strips_leading_trailing_dashes(self):
        self.assertEqual(slugify_id("--Hello--"), "hello")

    def test_handles_unicode_by_stripping(self):
        self.assertEqual(slugify_id("Oracel Cloud Korea 1"), "oracel-cloud-korea-1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_export_profiles_json -v`
Expected: FAIL — `ImportError: cannot import name 'slugify_id'`.

- [ ] **Step 3: Write minimal implementation**

Insert into `iterm2_to_ghostty.py` immediately after the end of `select_profile` (after line 272, before `escape_value`):

```python
def slugify_id(name: str) -> str:
    """Derive a stable, URL-safe id slug from an iTerm2 profile name.

    Lowercases, replaces runs of non-alphanumeric characters with a single dash,
    and strips leading/trailing dashes. Non-ASCII characters are dropped.
    """
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "-", str(name)).strip("-").lower()
    return cleaned or "profile"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_export_profiles_json -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add iterm2_to_ghostty.py tests/test_export_profiles_json.py
git commit -m "Add slugify_id helper for profile ids"
```

---

## Task 2: Profile type detection

**Files:**
- Modify: `iterm2_to_ghostty.py` (add `detect_type` after `slugify_id`)
- Test: `tests/test_export_profiles_json.py` (add a test class)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export_profiles_json.py` (before the `if __name__` block):

```python
from iterm2_to_ghostty import detect_type


class DetectTypeTests(unittest.TestCase):
    def test_ssh_when_command_starts_with_ssh(self):
        bm = {"Command": "ssh jack@ubuntu1.jyang.eu.org", "Custom Command": "No"}
        self.assertEqual(detect_type(bm), "ssh")

    def test_ssh_with_absolute_path(self):
        bm = {"Command": "/usr/bin/ssh -p 22 jack@host", "Custom Command": "Yes"}
        self.assertEqual(detect_type(bm), "ssh")

    def test_command_when_custom_command_yes_and_non_ssh(self):
        bm = {"Command": "docker compose up", "Custom Command": "Yes"}
        self.assertEqual(detect_type(bm), "command")

    def test_shell_when_custom_command_no_with_cd_leftover(self):
        bm = {"Command": "cd", "Custom Command": "No", "Working Directory": "/x/y"}
        self.assertEqual(detect_type(bm), "shell")

    def test_shell_when_no_command(self):
        bm = {"Custom Command": "No", "Working Directory": "/x/y"}
        self.assertEqual(detect_type(bm), "shell")

    def test_shell_treats_login_shell_as_shell(self):
        bm = {"Command": "/bin/zsh", "Custom Command": "No"}
        self.assertEqual(detect_type(bm), "shell")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_export_profiles_json.DetectTypeTests -v`
Expected: FAIL — `ImportError: cannot import name 'detect_type'`.

- [ ] **Step 3: Write minimal implementation**

Insert into `iterm2_to_ghostty.py` right after `slugify_id`:

```python
def detect_type(bookmark: dict[str, Any]) -> str:
    """Classify a bookmark as 'ssh', 'command', or 'shell'.

    Rules (see spec §3):
      1. Command's first token is `ssh` or ends with `/ssh` -> 'ssh'.
      2. Custom Command in {Yes, Custom} and a non-shell command is set -> 'command'.
      3. Otherwise -> 'shell' (plain interactive shell, possibly in a cwd).
    """
    raw_cmd = str(bookmark.get("Command", "") or "").strip()
    custom = str(bookmark.get("Custom Command", "No"))
    tokens = raw_cmd.split()
    if tokens:
        first = tokens[0].lower()
        if first == "ssh" or first.endswith("/ssh"):
            return "ssh"
    if custom in ("Yes", "Custom") and raw_cmd:
        first = tokens[0].lower()
        if first not in ("ssh",) and not first.endswith("/ssh"):
            if not _looks_like_login_shell(first):
                return "command"
    return "shell"


def _looks_like_login_shell(first_token: str) -> bool:
    """Heuristic: treat common shell/login program basenames as 'shell'."""
    basenames = {"zsh", "bash", "sh", "fish", "login", "cd"}
    return first_token in basenames or any(
        first_token.endswith(f"/{b}") for b in basenames
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_export_profiles_json.DetectTypeTests -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add iterm2_to_ghostty.py tests/test_export_profiles_json.py
git commit -m "Add detect_type classifier for ssh/command/shell"
```

---

## Task 3: Tag extraction helpers

**Files:**
- Modify: `iterm2_to_ghostty.py` (add five small helpers after `_looks_like_login_shell`)
- Test: `tests/test_export_profiles_json.py` (add test classes)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export_profiles_json.py`:

```python
from iterm2_to_ghostty import (
    name_tokens,
    prefix_bucket,
    ssh_tokens,
    path_segments,
    command_tokens,
)


class NameTokensTests(unittest.TestCase):
    def test_splits_on_spaces_and_case(self):
        self.assertEqual(
            name_tokens("BeCon Micro-Services China QA"),
            ["becon", "micro", "services", "china", "qa"],
        )

    def test_drops_empty_and_short(self):
        self.assertEqual(name_tokens("A B cc"), ["cc"])

    def test_lowercases(self):
        self.assertEqual(name_tokens("NAS"), ["nas"])


class PrefixBucketTests(unittest.TestCase):
    def test_becon(self):
        self.assertEqual(prefix_bucket("BeCon Micro-Services"), "becon")

    def test_scp(self):
        self.assertEqual(prefix_bucket("SCP BLE SDK"), "scp")

    def test_cloud_for_oracel(self):
        self.assertEqual(prefix_bucket("Oracel Cloud Korea 1"), "cloud")

    def test_home_for_nas(self):
        self.assertEqual(prefix_bucket("NAS2"), "home")

    def test_misc_default(self):
        self.assertEqual(prefix_bucket("Go Bootcamp"), "dev")
        self.assertEqual(prefix_bucket("Something Weird"), "misc")


class SshTokensTests(unittest.TestCase):
    def test_user_and_host_and_domain(self):
        self.assertEqual(
            ssh_tokens("ssh jack@ubuntu1.jyang.eu.org"),
            ["jack", "ubuntu1", "jyang", "eu", "org"],
        )

    def test_host_only(self):
        self.assertEqual(ssh_tokens("ssh nas.local"), ["nas", "local"])

    def test_empty_when_not_ssh(self):
        self.assertEqual(ssh_tokens("docker compose up"), [])


class PathSegmentsTests(unittest.TestCase):
    def test_drops_username_and_users(self):
        self.assertEqual(
            path_segments("/Users/jack/workspaces/becon/beco.cloud.connectivity"),
            ["workspaces", "becon", "beco", "cloud", "connectivity"],
        )

    def test_short_segments_dropped(self):
        self.assertEqual(path_segments("/Users/jack/a/bccc"), ["bccc"])

    def test_empty_for_home(self):
        self.assertEqual(path_segments("/Users/jack"), [])


class CommandTokensTests(unittest.TestCase):
    def test_drops_stopwords(self):
        self.assertEqual(
            sorted(command_tokens("cd ~/work && docker compose up")),
            ["compose", "docker"],
        )

    def test_empty_for_just_cd(self):
        self.assertEqual(command_tokens("cd"), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_export_profiles_json.NameTokensTests tests.test_export_profiles_json.PrefixBucketTests tests.test_export_profiles_json.SshTokensTests tests.test_export_profiles_json.PathSegmentsTests tests.test_export_profiles_json.CommandTokensTests -v`
Expected: FAIL — `ImportError` for the five names.

- [ ] **Step 3: Write minimal implementation**

Insert into `iterm2_to_ghostty.py` right after `_looks_like_login_shell`:

```python
PREFIX_BUCKETS = [
    ("BeCon", "becon"),
    ("SCP", "scp"),
    ("Perficient", "perficient"),
    ("Azure", "cloud"),
    ("Oracel", "cloud"),
    ("Oracle", "cloud"),
    ("Bosch", "cloud"),
    ("AlwaysData", "cloud"),
    ("Serv00", "cloud"),
    ("Mi", "home"),
    ("NAS", "home"),
    ("Home", "home"),
    ("iPhone", "home"),
    ("Router", "home"),
    ("AI", "ai"),
    ("Go Bootcamp", "dev"),
    ("IndexTTS", "dev"),
    ("Growth with Kids", "dev"),
]
DEV_NAMES = {"Go Bootcamp", "IndexTTS", "Growth with Kids"}
COMMAND_STOPWORDS = {
    "cd", "sudo", "and", "&&", "||", "|", ";", "echo", "exec", "source",
    ".", "~", "../", "./", "bash", "sh", "zsh",
}


def name_tokens(name: str) -> list[str]:
    """Split a profile name into lowercase search tokens."""
    split = re.split(r"[\s\-_/\\]+|(?<=[a-z])(?=[A-Z])", str(name))
    return [t.lower() for t in split if len(t) >= 3]


def prefix_bucket(name: str) -> str:
    """Return a single coarse category tag based on the profile name prefix."""
    n = str(name)
    for prefix, bucket in PREFIX_BUCKETS:
        if n.startswith(prefix):
            if bucket == "dev" and n not in DEV_NAMES:
                continue
            return bucket
    return "misc"


def ssh_tokens(command: str) -> list[str]:
    """Extract user, hostname, and domain segments from an ssh command."""
    tokens = str(command).split()
    if not tokens or tokens[0].lower() not in ("ssh",) and not tokens[0].endswith("/ssh"):
        return []
    target = ""
    for tok in tokens[1:]:
        if tok.startswith("-"):
            continue
        target = tok
        break
    if "@" in target:
        user, _, host = target.partition("@")
    else:
        user, host = "", target
    result: list[str] = []
    if user:
        result.append(user.lower())
    host = host.split(":")[0]  # strip any port
    for seg in host.split("."):
        if seg and len(seg) >= 2:
            result.append(seg.lower())
    return result


def path_segments(path: str) -> list[str]:
    """Return non-trivial path segments, dropping /Users/<username>."""
    parts = [p for p in str(path).split("/") if p]
    # Drop leading "Users" and the following username segment.
    if parts and parts[0] == "Users" and len(parts) >= 2:
        parts = parts[2:]
    return [p.lower() for p in parts if len(p) >= 3]


def command_tokens(command: str) -> list[str]:
    """Return non-stopword tokens from a command string."""
    tokens = re.split(r"[\s&|;]+", str(command))
    return [t.lower() for t in tokens if len(t) >= 3 and t.lower() not in COMMAND_STOPWORDS]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_export_profiles_json.NameTokensTests tests.test_export_profiles_json.PrefixBucketTests tests.test_export_profiles_json.SshTokensTests tests.test_export_profiles_json.PathSegmentsTests tests.test_export_profiles_json.CommandTokensTests -v`
Expected: PASS (all tests across the five classes).

- [ ] **Step 5: Commit**

```bash
git add iterm2_to_ghostty.py tests/test_export_profiles_json.py
git commit -m "Add tag extraction helpers (name/prefix/ssh/path/command)"
```

---

## Task 4: Full profile normalization

**Files:**
- Modify: `iterm2_to_ghostty.py` (add `extract_tags` and `normalize_profile` after the helpers above)
- Test: `tests/test_export_profiles_json.py` (add test class)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export_profiles_json.py`:

```python
from iterm2_to_ghostty import normalize_profile


class NormalizeProfileTests(unittest.TestCase):
    def test_ssh_profile_shape(self):
        bm = {
            "Name": "Perficient PC Ubuntu",
            "Guid": "FC192D07-5633-4AD2-8D54-B43A9D76ADFA",
            "Custom Command": "No",
            "Command": "ssh jack@ubuntu1.jyang.eu.org",
            "Custom Directory": "No",
            "Working Directory": "/Users/jack",
        }
        result = normalize_profile(bm)
        self.assertEqual(result["id"], "perficient-pc-ubuntu")
        self.assertEqual(result["name"], "Perficient PC Ubuntu")
        self.assertEqual(result["type"], "ssh")
        self.assertEqual(result["command"], "ssh jack@ubuntu1.jyang.eu.org")
        self.assertEqual(result["working_directory"], "/Users/jack")
        self.assertIn("ubuntu1", result["tags"])
        self.assertIn("perficient", result["tags"])
        self.assertTrue(result["tags"] == sorted(result["tags"]))  # sorted for stability
        self.assertFalse(result["skip"])
        self.assertEqual(result["raw"]["Guid"], "FC192D07-5633-4AD2-8D54-B43A9D76ADFA")

    def test_shell_profile_has_null_command(self):
        bm = {
            "Name": "BeCon Micro-Services",
            "Custom Command": "No",
            "Command": "cd",
            "Custom Directory": "Yes",
            "Working Directory": "/Users/jack/workspaces/becon/beco.cloud.connectivity",
        }
        result = normalize_profile(bm)
        self.assertEqual(result["type"], "shell")
        self.assertIsNone(result["command"])
        self.assertEqual(
            result["working_directory"],
            "/Users/jack/workspaces/becon/beco.cloud.connectivity",
        )
        self.assertIn("becon", result["tags"])
        self.assertIn("connectivity", result["tags"])

    def test_default_profile_is_skipped(self):
        bm = {"Name": "Default", "Command": "/bin/zsh", "Custom Command": "No"}
        result = normalize_profile(bm)
        self.assertTrue(result["skip"])

    def test_tags_are_deduped_and_lowercased(self):
        bm = {
            "Name": "NAS NAS",
            "Command": "ssh admin@nas.local",
            "Custom Command": "No",
        }
        result = normalize_profile(bm)
        self.assertEqual(len(result["tags"]), len(set(result["tags"])))
        self.assertTrue(all(t == t.lower() for t in result["tags"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_export_profiles_json.NormalizeProfileTests -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_profile'`.

- [ ] **Step 3: Write minimal implementation**

Insert into `iterm2_to_ghostty.py` right after `command_tokens`:

```python
def extract_tags(bookmark: dict[str, Any], profile_type: str) -> list[str]:
    """Aggregate, dedupe, lowercase, and sort all search tags for a profile."""
    name = str(bookmark.get("Name", ""))
    raw_cmd = str(bookmark.get("Command", "") or "")
    wd = str(bookmark.get("Working Directory", "") or "")
    collected: set[str] = set()
    collected.update(name_tokens(name))
    collected.add(prefix_bucket(name))
    if profile_type == "ssh":
        collected.update(ssh_tokens(raw_cmd))
    collected.update(path_segments(wd))
    if profile_type == "command":
        collected.update(command_tokens(raw_cmd))
    collected.discard("")
    return sorted(collected)


def normalize_profile(bookmark: dict[str, Any]) -> dict[str, Any]:
    """Normalize one iTerm2 bookmark dict into the profiles.json shape (spec §3)."""
    name = str(bookmark.get("Name", "") or "<unnamed>")
    profile_type = detect_type(bookmark)
    raw_cmd = str(bookmark.get("Command", "") or "").strip()
    custom_dir = str(bookmark.get("Custom Directory", "No"))
    wd_raw = str(bookmark.get("Working Directory", "") or "").strip()
    working_directory = wd_raw if wd_raw and custom_dir in ("Yes", "Custom") else (
        wd_raw if wd_raw and profile_type != "shell" else (wd_raw or None)
    )
    command: str | None
    if profile_type in ("ssh", "command"):
        command = raw_cmd or None
    else:
        command = None
    skip = (name == "Default")
    return {
        "id": slugify_id(name),
        "name": name,
        "type": profile_type,
        "working_directory": working_directory,
        "command": command,
        "tags": extract_tags(bookmark, profile_type),
        "skip": skip,
        "raw": {
            "Guid": bookmark.get("Guid"),
            "Custom Command": bookmark.get("Custom Command"),
            "Command": bookmark.get("Command"),
            "Working Directory": bookmark.get("Working Directory"),
            "Custom Directory": bookmark.get("Custom Directory"),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_export_profiles_json.NormalizeProfileTests -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add iterm2_to_ghostty.py tests/test_export_profiles_json.py
git commit -m "Add normalize_profile producing profiles.json shape"
```

---

## Task 5: Export mode wiring (`--export-profiles-json`)

**Files:**
- Modify: `iterm2_to_ghostty.py` (`export_profiles_json` helper + CLI flag in `parse_args` + dispatch in `main`)
- Test: `tests/test_export_profiles_json.py` (add a test class)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_export_profiles_json.py`:

```python
import json
import tempfile
from iterm2_to_ghostty import build_profiles_document


class BuildProfilesDocumentTests(unittest.TestCase):
    def test_includes_all_non_skip_profiles_sorted_by_id(self):
        prefs = {
            "New Bookmarks": [
                {"Name": "Zeta", "Command": "ssh a@z", "Custom Command": "No"},
                {"Name": "Default", "Command": "/bin/zsh", "Custom Command": "No"},
                {"Name": "Alpha", "Command": "cd", "Custom Command": "No",
                 "Working Directory": "/x", "Custom Directory": "Yes"},
            ]
        }
        doc = build_profiles_document(prefs, dynamic_dir=None)
        names = [p["name"] for p in doc["profiles"]]
        self.assertEqual(names, ["Alpha", "Zeta"])  # Default skipped, sorted by id
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(doc["source"], "com.googlecode.iterm2")
        self.assertIn("exported_at", doc)

    def test_idempotent_profiles_array(self):
        prefs = {"New Bookmarks": [
            {"Name": "B", "Command": "ssh b@host", "Custom Command": "No"},
            {"Name": "A", "Command": "ssh a@host", "Custom Command": "No"},
        ]}
        d1 = build_profiles_document(prefs, None)
        d2 = build_profiles_document(prefs, None)
        # exported_at may differ; profiles array must be byte-identical.
        self.assertEqual(d1["profiles"], d2["profiles"])

    def test_empty_when_no_bookmarks(self):
        doc = build_profiles_document({"New Bookmarks": []}, None)
        self.assertEqual(doc["profiles"], [])
```

Also add `build_profiles_document` to the existing import line at the top of the file:

```python
from iterm2_to_ghostty import (
    slugify_id,
    detect_type,
    name_tokens,
    prefix_bucket,
    ssh_tokens,
    path_segments,
    command_tokens,
    normalize_profile,
    build_profiles_document,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_export_profiles_json.BuildProfilesDocumentTests -v`
Expected: FAIL — `ImportError: cannot import name 'build_profiles_document'`.

- [ ] **Step 3: Write minimal implementation**

Insert into `iterm2_to_ghostty.py` right after `normalize_profile`:

```python
def build_profiles_document(
    prefs: dict[str, Any], dynamic_dir: Path | None
) -> dict[str, Any]:
    """Build the full profiles.json document from iTerm2 preferences (spec §3)."""
    from datetime import datetime, timezone

    bookmarks = all_profiles(prefs, dynamic_dir)
    normalized = [normalize_profile(b) for b in bookmarks if isinstance(b, dict)]
    # Keep skipped profiles OUT of the document entirely (cleaner for the UI).
    normalized = [p for p in normalized if not p.get("skip")]
    normalized.sort(key=lambda p: p["id"])
    return {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": ITERM_DOMAIN,
        "profiles": normalized,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_export_profiles_json.BuildProfilesDocumentTests -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Add the CLI flag and dispatch**

In `parse_args` (around line 815, after the `--list-profiles` block), add:

```python
    parser.add_argument(
        "--export-profiles-json",
        type=Path,
        nargs="?",
        const=Path.home() / ".config" / "ghostty" / "profiles.json",
        help="Export ALL iTerm2 profiles to a normalized JSON file for the Raycast "
        "extension. Writes to the given path, or ~/.config/ghostty/profiles.json "
        "if no path is given.",
    )
```

In `main`, immediately after the `if args.list_profiles:` block (before `profile = select_profile(...)`), add:

```python
    if args.export_profiles_json is not None:
        document = build_profiles_document(prefs, args.dynamic_profiles_dir)
        payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        if args.dry_run:
            sys.stdout.write(payload)
        else:
            output_path: Path = args.export_profiles_json
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(payload, encoding="utf-8")
            print(f"Wrote {len(document['profiles'])} profiles to {output_path}")
        return 0
```

- [ ] **Step 6: Smoke-test the end-to-end export**

Run: `./iterm2_to_ghostty.py --export-profiles-json --dry-run | python3 -m json.tool > /dev/null && echo OK`
Expected: prints `OK` (valid JSON to stdout).

Then write the real file: `./iterm2_to_ghostty.py --export-profiles-json`
Expected: prints `Wrote <N> profiles to /Users/jack/.config/ghostty/profiles.json`.

Spot-check one entry: `python3 -c "import json; d=json.load(open('$HOME/.config/ghostty/profiles.json')); print([p for p in d['profiles'] if p['name']=='Perficient PC Ubuntu'][0])"`
Expected: a dict with `"type": "ssh"`, a populated `tags` list including `ubuntu1`, and the right `command`.

- [ ] **Step 7: Run the full Python test suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests PASS (existing conversion tests + new export tests).

Run: `python3 -m py_compile iterm2_to_ghostty.py && echo COMPILE_OK`
Expected: `COMPILE_OK`.

- [ ] **Step 8: Commit**

```bash
git add iterm2_to_ghostty.py tests/test_export_profiles_json.py
git commit -m "Add --export-profiles-json CLI mode writing profiles.json"
```

---

## Task 6: Scaffold the Raycast extension

**Files:**
- Create: `raycast-extension/package.json`
- Create: `raycast-extension/tsconfig.json`
- Create: `raycast-extension/vitest.config.ts`
- Create: `raycast-extension/.gitignore`
- Create: `raycast-extension/assets/icon.png` (generated)
- Create: `raycast-extension/src/index.tsx` (placeholder, smoke test)
- Create: `raycast-extension/.npmrc`

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p raycast-extension/src/__tests__ raycast-extension/assets
```

- [ ] **Step 2: Write `raycast-extension/package.json`**

```json
{
  "name": "iterm-ghostty-profiles",
  "title": "iTerm Profiles for Ghostty",
  "description": "Search exported iTerm2 profiles and open them as Ghostty tabs/windows.",
  "icon": "assets/icon.png",
  "author": "jack",
  "platforms": ["macOS"],
  "categories": ["Productivity", "Developer Tools"],
  "license": "MIT",
  "commands": [
    {
      "name": "index",
      "title": "Search iTerm Profiles",
      "description": "Search exported iTerm2 profiles and open in Ghostty.",
      "mode": "view",
      "keywords": ["iterm", "ghostty", "terminal", "ssh"]
    }
  ],
  "dependencies": {
    "@raycast/api": "^1.95.0",
    "react": "^18.3.1"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@types/react": "^18.3.0",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0"
  },
  "scripts": {
    "build": "ray build",
    "dev": "ray develop",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 3: Write `raycast-extension/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM"],
    "jsx": "react-jsx",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "types": ["node"]
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Write `raycast-extension/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/__tests__/**/*.test.ts"],
    environment: "node",
  },
});
```

- [ ] **Step 5: Write `raycast-extension/.gitignore` and `.npmrc`**

`.gitignore`:
```
node_modules/
dist/
.DS_Store
*.log
```

`.npmrc`:
```
engine-strict=true
```

- [ ] **Step 6: Generate `raycast-extension/assets/icon.png`**

```bash
python3 - <<'EOF'
import zlib, struct, pathlib
def png(path, w=512, h=512, rgb=(60, 90, 140)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    pathlib.Path(path).write_bytes(data)
png("raycast-extension/assets/icon.png")
print("icon written")
EOF
```
Expected: prints `icon written`.

- [ ] **Step 7: Write a placeholder `raycast-extension/src/index.tsx`**

```tsx
import React from "react";
import { List } from "@raycast/api";

export default function Command() {
  return (
    <List>
      <List.Item title="Scaffold OK" />
    </List>
  );
}
```

- [ ] **Step 8: Install dependencies**

Run: `npm install` (in `raycast-extension/`)
Expected: completes; `node_modules/` created; no errors.

- [ ] **Step 9: Smoke-test in Raycast**

Run: `npm run dev` (in `raycast-extension/`)
Expected: Raycast opens with the "Search iTerm Profiles" command showing a single "Scaffold OK" item. Stop the dev server (Ctrl+C) once confirmed.

- [ ] **Step 10: Commit**

```bash
git add raycast-extension
git commit -m "Scaffold Raycast extension for iTerm/Ghostty profiles"
```

---

## Task 7: TypeScript `Profile` type + JSON loader

**Files:**
- Create: `raycast-extension/src/types.ts`
- Create: `raycast-extension/src/profiles.ts`
- Test: `raycast-extension/src/__tests__/profiles.test.ts`

- [ ] **Step 1: Write the failing test**

Create `raycast-extension/src/__tests__/profiles.test.ts`:

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadProfiles, ProfilesError } from "../profiles";

const tmp = join(tmpdir(), "raycast-profiles-test");

beforeEach(() => {
  mkdirSync(tmp, { recursive: true });
});
afterEach(() => {
  rmSync(tmp, { recursive: true, force: true });
});

describe("loadProfiles", () => {
  it("returns the profiles array when the JSON is valid", () => {
    const path = join(tmp, "profiles.json");
    writeFileSync(
      path,
      JSON.stringify({
        schema_version: 1,
        exported_at: "2026-07-05T00:00:00Z",
        source: "com.googlecode.iterm2",
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
    const result = loadProfiles(path);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("NAS");
  });

  it("throws ProfilesError when the file is missing", () => {
    expect(() => loadProfiles(join(tmp, "nope.json"))).toThrow(ProfilesError);
  });

  it("throws ProfilesError when JSON is malformed", () => {
    const path = join(tmp, "bad.json");
    writeFileSync(path, "{ not json");
    expect(() => loadProfiles(path)).toThrow(ProfilesError);
  });

  it("throws ProfilesError when schema_version is absent", () => {
    const path = join(tmp, "noschema.json");
    writeFileSync(path, JSON.stringify({ profiles: [] }));
    expect(() => loadProfiles(path)).toThrow(ProfilesError);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test` (in `raycast-extension/`)
Expected: FAIL — `Cannot find module '../profiles'`.

- [ ] **Step 3: Write `raycast-extension/src/types.ts`**

```typescript
export type ProfileType = "ssh" | "shell" | "command";

export interface Profile {
  id: string;
  name: string;
  type: ProfileType;
  working_directory: string | null;
  command: string | null;
  tags: string[];
  skip: boolean;
  raw: Record<string, unknown>;
}

export interface ProfilesDocument {
  schema_version: number;
  exported_at: string;
  source: string;
  profiles: Profile[];
}
```

- [ ] **Step 4: Write `raycast-extension/src/profiles.ts`**

```typescript
import { readFileSync } from "node:fs";
import type { Profile, ProfilesDocument } from "./types";

export class ProfilesError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProfilesError";
  }
}

/** Default location the Python export script writes to. */
export const DEFAULT_PROFILES_PATH =
  process.env.HOME + "/.config/ghostty/profiles.json";

/** Load and validate profiles.json. Throws ProfilesError on any problem. */
export function loadProfiles(path: string = DEFAULT_PROFILES_PATH): Profile[] {
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
  return doc.profiles.filter((p) => p && !p.skip) as Profile[];
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add raycast-extension/src/types.ts raycast-extension/src/profiles.ts raycast-extension/src/__tests__/profiles.test.ts
git commit -m "Add Profile type and JSON loader with validation"
```

---

## Task 8: AppleScript generator (pure functions)

**Files:**
- Create: `raycast-extension/src/applescript.ts`
- Test: `raycast-extension/src/__tests__/applescript.test.ts`

- [ ] **Step 1: Write the failing test**

Create `raycast-extension/src/__tests__/applescript.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { buildAppleScript, escapeAppleString } from "../applescript";
import type { Profile } from "../types";

function p(over: Partial<Profile>): Profile {
  return {
    id: "x",
    name: "X",
    type: "shell",
    working_directory: null,
    command: null,
    tags: [],
    skip: false,
    raw: {},
    ...over,
  };
}

describe("escapeAppleString", () => {
  it("escapes backslashes and double quotes", () => {
    expect(escapeAppleString('a"b\\c')).toBe('a\\"b\\\\c');
  });
});

describe("buildAppleScript", () => {
  it("ssh in a new tab uses command of cfg", () => {
    const script = buildAppleScript(p({ type: "ssh", command: "ssh jack@host" }), "tab");
    expect(script).toContain('set command of cfg to "ssh jack@host"');
    expect(script).toContain("set t to new tab with configuration cfg");
    expect(script).toContain("set w to new window with configuration cfg");
  });

  it("shell in a new tab sets initial working directory and no command", () => {
    const script = buildAppleScript(
      p({ type: "shell", working_directory: "/Users/jack/work/x" }),
      "tab"
    );
    expect(script).toContain('set initial working directory of cfg to "/Users/jack/work/x"');
    expect(script).not.toContain("set command of cfg");
  });

  it("new window target always uses new window", () => {
    const script = buildAppleScript(p({ type: "ssh", command: "ssh a@b" }), "window");
    expect(script).toContain("set w to new window with configuration cfg");
    expect(script).not.toContain("new tab");
  });

  it("escapes a quote inside the command", () => {
    const script = buildAppleScript(
      p({ type: "ssh", command: 'ssh jack@host -t "tmux a"' }),
      "tab"
    );
    expect(script).toContain('set command of cfg to "ssh jack@host -t \\"tmux a\\""');
  });

  it("split target creates a tab then splits right", () => {
    const script = buildAppleScript(p({ type: "shell", working_directory: "/x" }), "split");
    expect(script).toContain("set t to new tab with configuration cfg");
    expect(script).toContain("split t direction right with configuration cfg");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Cannot find module '../applescript'`.

- [ ] **Step 3: Write `raycast-extension/src/applescript.ts`**

```typescript
import type { Profile } from "./types";

export type LaunchTarget = "tab" | "window" | "split";

/** Escape a string for safe interpolation into an AppleScript double-quoted literal. */
export function escapeAppleString(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

/**
 * Build a Ghostty AppleScript that opens the given profile.
 * `tab`: new tab in the frontmost window (falls back to a new window if none).
 * `window`: always a new window.
 * `split`: new tab, then split right (low-priority action).
 */
export function buildAppleScript(profile: Profile, target: LaunchTarget): string {
  const lines: string[] = [];
  lines.push("tell application \"Ghostty\"");
  lines.push("  set cfg to new surface configuration");

  if (profile.command && (profile.type === "ssh" || profile.type === "command")) {
    lines.push(`  set command of cfg to "${escapeAppleString(profile.command)}"`);
  } else if (profile.working_directory) {
    lines.push(
      `  set initial working directory of cfg to "${escapeAppleString(profile.working_directory)}"`
    );
  }

  if (target === "window") {
    lines.push("  set w to new window with configuration cfg");
  } else if (target === "split") {
    lines.push("  if (count of windows) > 0 then");
    lines.push("    set t to new tab with configuration cfg");
    lines.push("  else");
    lines.push("    set w to new window with configuration cfg");
    lines.push("  end if");
    lines.push("  split t direction right with configuration cfg");
  } else {
    lines.push("  if (count of windows) > 0 then");
    lines.push("    set t to new tab with configuration cfg");
    lines.push("  else");
    lines.push("    set w to new window with configuration cfg");
    lines.push("  end if");
  }
  lines.push("  activate");
  lines.push("end tell");
  return lines.join("\n");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`
Expected: PASS (all tests in applescript.test.ts and profiles.test.ts).

- [ ] **Step 5: Commit**

```bash
git add raycast-extension/src/applescript.ts raycast-extension/src/__tests__/applescript.test.ts
git commit -m "Add AppleScript generator for tab/window/split targets"
```

---

## Task 9: Raycast `List` UI + actions

**Files:**
- Modify: `raycast-extension/src/index.tsx` (replace placeholder)

- [ ] **Step 1: Replace `raycast-extension/src/index.tsx` with the full UI**

```tsx
import React, { useState, useCallback } from "react";
import {
  Action,
  ActionPanel,
  Clipboard,
  Icon,
  List,
  showToast,
  Toast,
} from "@raycast/api";
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { loadProfiles, DEFAULT_PROFILES_PATH, ProfilesError } from "./profiles";
import { buildAppleScript, LaunchTarget } from "./applescript";
import type { Profile } from "./types";

function iconForType(type: Profile["type"]) {
  switch (type) {
    case "ssh":
      return Icon.Globe;
    case "command":
      return Icon.Gear;
    default:
      return Icon.Terminal;
  }
}

function subtitleFor(profile: Profile): string {
  if (profile.command) return profile.command;
  if (profile.working_directory) return profile.working_directory;
  return "(default shell)";
}

/** Run the AppleScript via osascript. Shows a toast on failure. */
function runGhostty(script: string) {
  execFile("osascript", ["-e", script], (err) => {
    if (err) {
      showToast({
        style: Toast.Style.Failure,
        title: "Ghostty launch failed",
        message: err.message,
      });
    }
  });
}

function makeActions(profile: Profile) {
  const launch = (target: LaunchTarget) => () => runGhostty(buildAppleScript(profile, target));
  return (
    <ActionPanel>
      <Action title="Open in New Tab" icon={Icon.Plus} onAction={launch("tab")} />
      <Action
        title="Open in New Window"
        icon={Icon.Window}
        shortcut={{ modifiers: ["cmd"], key: "return" }}
        onAction={launch("window")}
      />
      <Action
        title="Open as Split Pane (Right)"
        icon={Icon.ArrowRight}
        onAction={launch("split")}
      />
      {profile.command ? (
        <Action
          title="Copy Command"
          icon={Icon.Clipboard}
          shortcut={{ modifiers: ["cmd", "shift"], key: "c" }}
          onAction={() => {
            Clipboard.copy(profile.command || "");
            showToast({ style: Toast.Style.Success, title: "Command copied" });
          }}
        />
      ) : null}
      {profile.working_directory ? (
        <Action.Open
          title="Reveal Working Directory"
          icon={Icon.Folder}
          target={profile.working_directory}
        />
      ) : null}
    </ActionPanel>
  );
}

export default function Command() {
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);

  let profiles: Profile[] = [];
  let loadError: string | null = null;
  const fileExists = existsSync(DEFAULT_PROFILES_PATH);

  try {
    profiles = loadProfiles();
  } catch (err) {
    if (err instanceof ProfilesError) {
      loadError = err.message;
    } else {
      loadError = (err as Error).message;
    }
  }

  if (loadError) {
    return (
      <List>
        <List.Item
          icon={Icon.ExclamationMark}
          title="No profiles loaded"
          subtitle={loadError}
          accessories={fileExists ? [] : [{ text: "run the export script" }]}
          actions={
            <ActionPanel>
              <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
            </ActionPanel>
          }
        />
      </List>
    );
  }

  if (profiles.length === 0) {
    return (
      <List>
        <List.Item
          icon={Icon.Document}
          title="No profiles exported yet"
          subtitle="Run: ./iterm2_to_ghostty.py --export-profiles-json"
          actions={
            <ActionPanel>
              <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
            </ActionPanel>
          }
        />
      </List>
    );
  }

  return (
    <List
      key={version}
      navigationTitle="iTerm Profiles"
      searchBarPlaceholder="Search profiles by name, host, tag…"
      actions={
        <ActionPanel>
          <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
        </ActionPanel>
      }
    >
      {profiles.map((profile) => (
        <List.Item
          key={profile.id}
          id={profile.id}
          icon={iconForType(profile.type)}
          title={profile.name}
          subtitle={subtitleFor(profile)}
          accessories={profile.tags.slice(0, 3).map((t) => ({ tag: t }))}
          keywords={[profile.name, ...profile.tags, profile.command || ""]}
          actions={makeActions(profile)}
        />
      ))}
    </List>
  );
}
```

> Note: `environment` is imported but unused in MVP; remove it if the TS compiler complains (strict mode). Keep the import only if referenced. If `tsc --noEmit` flags it, delete the `environment` import line.

- [ ] **Step 2: Type-check**

Run: `npx tsc --noEmit` (in `raycast-extension/`)
Expected: no errors.

- [ ] **Step 3: Run unit tests (regression)**

Run: `npm test`
Expected: PASS (unchanged: applescript + profiles tests).

- [ ] **Step 4: Commit**

```bash
git add raycast-extension/src/index.tsx
git commit -m "Implement searchable profile list with launch actions"
```

---

## Task 10: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Ensure `profiles.json` exists**

Run: `ls -la ~/.config/ghostty/profiles.json`
If missing, run: `./iterm2_to_ghostty.py --export-profiles-json`
Expected: file present with `<N> profiles`.

- [ ] **Step 2: Launch the extension in Raycast**

Run: `cd raycast-extension && npm run dev`
Expected: Raycast opens "Search iTerm Profiles" with the full list visible.

- [ ] **Step 3: Verify search**

In the Raycast window, type each of these and confirm the right items remain:
- `ubuntu` → shows the Ubuntu SSH profiles
- `becon qa` → shows BeCon profiles whose name/tags contain "qa"
- `nas` → shows the NAS profiles
- `jack` → shows every SSH profile logging in as `jack`

- [ ] **Step 4: Verify the default action (new tab)**

Pick an SSH profile (e.g. `Perficient PC Ubuntu`), press Enter.
Expected: Ghostty comes to focus; a new tab opens and connects via SSH.

Pick a `shell` profile (e.g. `BeCon Micro-Services`), press Enter.
Expected: a new tab opens with an interactive shell in `/Users/jack/workspaces/becon/beco.cloud.connectivity`.

- [ ] **Step 5: Verify secondary actions**

On any profile, open the action panel (`⌘K`):
- `Open in New Window` (⌘↵) → opens a fresh Ghostty window.
- `Copy Command` → clipboard now contains the ssh/command string.
- `Reveal Working Directory` → opens that folder in Finder (only for profiles with a cwd).

- [ ] **Step 6: Verify empty/error state**

Temporarily move the JSON: `mv ~/.config/ghostty/profiles.json ~/.config/ghostty/profiles.json.bak`
Run the extension again. Expected: "No profiles loaded" with the "run the export script" accessory.
Restore: `mv ~/.config/ghostty/profiles.json.bak ~/.config/ghostty/profiles.json`
Press `Refresh` → list reappears.

- [ ] **Step 7: Stop the dev server, run the full test suites**

```bash
# Python
python3 -m unittest discover -s tests
python3 -m py_compile iterm2_to_ghostty.py
# TypeScript
cd raycast-extension && npm test && npx tsc --noEmit
```
Expected: all green.

- [ ] **Step 8: Final commit (docs touch-up if any)**

If any small fixes were made during verification, commit them. Otherwise this task produces no commit.

---

## Self-Review Notes (applied during authoring)

- **Spec coverage:** Every spec section maps to a task. §3 type rules → Task 2; §4 tags → Task 3; §3 normalize/§5 export → Tasks 4–5; §6 List/UX → Task 9; §7 AppleScript → Task 8; §8 errors → Task 9 (empty/error states) + Task 7 (loader errors); §9 tests → Tasks 1–5 (Python) and 7–8 (TS); §10 MVP scope → Tasks 1–10 (split/edit/auto-refresh deliberately deferred).
- **Type consistency:** `LaunchTarget = "tab" | "window" | "split"` matches between `applescript.ts` and `index.tsx`. `Profile` fields (`working_directory`, `command`, `tags`, `skip`) match between `types.ts`, the Python JSON shape (Task 4), and the loader (Task 7).
- **No placeholders:** every code step contains runnable code; no "TODO"/"add error handling".
- **Idempotency note:** `exported_at` is a timestamp so the full file is not byte-identical across runs; the idempotency test (Task 5) compares only the `profiles` array, which is the meaningful invariant.
