#!/usr/bin/env python3
"""
Convert iTerm2 profile settings to Ghostty configuration.

The converter reads iTerm2's plist preferences (including dynamic profiles),
selects an iTerm2 profile, and writes a Ghostty config plus optional light/dark
Ghostty theme files. It intentionally emits comments for settings that have no
Ghostty equivalent so the generated file is auditable rather than silently lossy.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ITERM_DOMAIN = "com.googlecode.iterm2"
DEFAULT_ITERM_PLIST = Path.home() / "Library/Preferences/com.googlecode.iterm2.plist"
DEFAULT_DYNAMIC_PROFILES_DIR = Path.home() / "Library/Application Support/iTerm2/DynamicProfiles"
DEFAULT_GHOSTTY_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ghostty"

ANSI_KEYS = [f"Ansi {i} Color" for i in range(16)]
BASE_COLOR_KEYS = {
    "background": "Background Color",
    "foreground": "Foreground Color",
    "cursor-color": "Cursor Color",
    "cursor-text": "Cursor Text Color",
    "selection-background": "Selection Color",
    "selection-foreground": "Selected Text Color",
}
LIGHT_DARK_SUFFIXES = {"light": " (Light)", "dark": " (Dark)"}

CURSOR_TYPES = {0: "underline", 1: "bar", 2: "block"}
OPTION_SENDS_ALT_VALUES = {1, 2, "1", "2"}  # META or ESC both aim at terminal alt/meta behavior.

# NSEvent modifier flags as stored in iTerm2 key map strings.
MODIFIER_MASKS = [
    (0x100000, "super"),
    (0x40000, "ctrl"),
    (0x80000, "alt"),
    (0x20000, "shift"),
]

SHIFTED_US_KEYS = {
    "~": "`",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "-",
    "+": "=",
    "{": "[",
    "}": "]",
    "|": "\\\\",
    ":": ";",
    '"': "'",
    "<": ",",
    ">": ".",
    "?": "/",
}

SPECIAL_KEYS = {
    0x7F: "backspace",
    0x09: "tab",
    0x0D: "enter",
    0x1B: "escape",
    0x20: "space",
    0xF700: "up",
    0xF701: "down",
    0xF702: "left",
    0xF703: "right",
    0xF704: "f1",
    0xF705: "f2",
    0xF706: "f3",
    0xF707: "f4",
    0xF708: "f5",
    0xF709: "f6",
    0xF70A: "f7",
    0xF70B: "f8",
    0xF70C: "f9",
    0xF70D: "f10",
    0xF70E: "f11",
    0xF70F: "f12",
    0xF710: "f13",
    0xF711: "f14",
    0xF712: "f15",
    0xF713: "f16",
    0xF714: "f17",
    0xF715: "f18",
    0xF716: "f19",
    0xF727: "insert",
    0xF728: "delete",
    0xF729: "home",
    0xF72B: "end",
    0xF72C: "page_up",
    0xF72D: "page_down",
}

UNSUPPORTED_PROFILE_KEYS = {
    "Triggers": "Ghostty has no direct trigger/coprocess equivalent.",
    "Smart Selection Rules": (
        "Ghostty supports selection word boundaries but not iTerm2 smart-selection actions."
    ),
    "Semantic History": (
        "Ghostty has URL/file link support but no direct semantic-history action model."
    ),
    "Bound Hosts": "Ghostty has no automatic profile switching equivalent.",
    "Badge Text": "Ghostty has no terminal badge overlay equivalent.",
    "Show Status Bar": "Ghostty has no iTerm2 status bar equivalent.",
    "Background Image Mode": "Only partially mapped; verify fit/position manually.",
    "Blend": "Ghostty background-image-opacity is not identical to iTerm2 blend.",
    "Disable Smcup Rmcup": "Ghostty does not expose an alternate-screen disable setting.",
    "Character Encoding": "Ghostty is UTF-8 oriented; legacy encodings are not mapped.",
    "Unicode Normalization": "No direct Ghostty equivalent.",
    "Thin Strokes": "Only approximate via font-thicken on macOS; not mapped automatically.",
}

@dataclass
class Conversion:
    config: list[str] = field(default_factory=list)
    light_theme: list[str] = field(default_factory=list)
    dark_theme: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


def plist_load(path: Path) -> Any:
    with path.open("rb") as f:
        return plistlib.load(f)


def load_iterm_preferences(path: Path | None) -> dict[str, Any]:
    if path:
        return plist_load(path)
    if DEFAULT_ITERM_PLIST.exists():
        return plist_load(DEFAULT_ITERM_PLIST)

    # defaults export sees preferences that have not necessarily been flushed to the plist file.
    try:
        proc = subprocess.run(
            ["defaults", "export", ITERM_DOMAIN, "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return plistlib.loads(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Could not read iTerm2 preferences. Pass --iterm-plist. Details: {exc}")


def load_dynamic_profiles(directory: Path | None) -> list[dict[str, Any]]:
    directory = directory or DEFAULT_DYNAMIC_PROFILES_DIR
    profiles: list[dict[str, Any]] = []
    if not directory.exists():
        return profiles
    for path in sorted(p for p in directory.iterdir() if p.is_file()):
        try:
            data = plist_load(path)
        except Exception:
            continue
        entries = data.get("Profiles", []) if isinstance(data, dict) else []
        for profile in entries:
            if isinstance(profile, dict):
                profile = dict(profile)
                profile.setdefault("__source", str(path))
                profiles.append(profile)
    return profiles


def all_profiles(prefs: dict[str, Any], dynamic_dir: Path | None) -> list[dict[str, Any]]:
    """Return iTerm2 profiles with Dynamic Profiles applied as overlays.

    iTerm2 Dynamic Profiles may contain complete profiles, but in practice they
    are often sparse updates identified by Guid. iTerm2 overlays them on top of
    the normal preferences profile with the same Guid. Do the same so selecting
    such a profile does not lose fonts/colors/window settings that only exist in
    the base profile.
    """
    profiles: list[dict[str, Any]] = []
    by_guid: dict[str, dict[str, Any]] = {}

    for profile in prefs.get("New Bookmarks", []):
        if not isinstance(profile, dict):
            continue
        copy = dict(profile)
        copy.setdefault("__source", "preferences")
        profiles.append(copy)
        guid = str(copy.get("Guid", ""))
        if guid:
            by_guid[guid] = copy

    for dynamic in load_dynamic_profiles(dynamic_dir):
        guid = str(dynamic.get("Guid", ""))
        if guid and guid in by_guid:
            source = dynamic.get("__source", "dynamic profile")
            merged = dict(by_guid[guid])
            merged.update(dynamic)
            merged["__source"] = f"{by_guid[guid].get('__source', 'preferences')} + {source}"
            by_guid[guid].clear()
            by_guid[guid].update(merged)
        else:
            profiles.append(dynamic)
            if guid:
                by_guid[guid] = dynamic

    return profiles


def select_profile(
    profiles: list[dict[str, Any]],
    prefs: dict[str, Any],
    selector: str | None,
) -> dict[str, Any]:
    if not profiles:
        raise SystemExit("No iTerm2 profiles found in preferences or dynamic profiles.")
    if selector:
        lower = selector.lower()
        matches = [
            p
            for p in profiles
            if str(p.get("Name", "")).lower() == lower
            or str(p.get("Guid", "")).lower() == lower
        ]
        if not matches:
            names = ", ".join(sorted(str(p.get("Name", "<unnamed>")) for p in profiles))
            raise SystemExit(f"Profile {selector!r} not found. Available profiles: {names}")
        return matches[0]

    default_guid = prefs.get("Default Bookmark Guid") or prefs.get("Default Bookmark GUID")
    if default_guid:
        for p in profiles:
            if p.get("Guid") == default_guid:
                return p
    for p in profiles:
        if p.get("Name") == "Default":
            return p
    return profiles[0]


def escape_value(value: Any) -> str:
    s = str(value)
    if not s:
        return '""'
    if re.search(r"\s|#|\"", s):
        return json.dumps(s)
    return s


def add_line(lines: list[str], key: str, value: Any) -> None:
    if value is None:
        return
    lines.append(f"{key} = {escape_value(value)}")


def bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def color_to_hex(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    try:
        r = float(value.get("Red Component", 0.0))
        g = float(value.get("Green Component", 0.0))
        b = float(value.get("Blue Component", 0.0))
    except (TypeError, ValueError):
        return None
    clamp = lambda x: max(0, min(255, int(round(x * 255))))
    # Ghostty accepts hex colors without '#'. Emitting bare RRGGBB avoids
    # needing value quoting and matches Ghostty's simple key/value syntax.
    return f"{clamp(r):02x}{clamp(g):02x}{clamp(b):02x}"


def parse_font(value: Any) -> tuple[str, float | None] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    match = re.match(r"^(?P<name>.*?)[ ,]+(?P<size>\d+(?:\.\d+)?)$", value.strip())
    if not match:
        return (value.strip(), None)
    name = match.group("name").strip()
    size = float(match.group("size"))
    return name, size


def maybe_color(profile: dict[str, Any], base_key: str, mode: str | None = None) -> str | None:
    key = base_key + (LIGHT_DARK_SUFFIXES.get(mode or "", ""))
    return color_to_hex(profile.get(key)) or color_to_hex(profile.get(base_key))


def emit_theme(profile: dict[str, Any], lines: list[str], mode: str | None = None) -> None:
    lines.append(f"# Colors converted from iTerm2 profile: {profile.get('Name', '<unnamed>')}")
    for ghostty_key, iterm_key in BASE_COLOR_KEYS.items():
        value = maybe_color(profile, iterm_key, mode)
        if value:
            add_line(lines, ghostty_key, value)
    bold = maybe_color(profile, "Bold Color", mode)
    if bold and profile.get("Use Bright Bold"):
        add_line(lines, "bold-color", bold)
    for i, iterm_key in enumerate(ANSI_KEYS):
        value = maybe_color(profile, iterm_key, mode)
        if value:
            lines.append(f"palette = {i}={value}")


def convert_font(profile: dict[str, Any], conv: Conversion) -> None:
    font = parse_font(profile.get("Normal Font"))
    if font:
        name, size = font
        add_line(conv.config, "font-family", name)
        if size:
            # Keep integers tidy but allow half-point sizes.
            add_line(conv.config, "font-size", int(size) if size.is_integer() else size)
    if profile.get("Use Non-ASCII Font"):
        non_ascii = parse_font(profile.get("Non Ascii Font"))
        if non_ascii:
            add_line(conv.config, "font-family", non_ascii[0])
            conv.warnings.append(
                "Added iTerm2 Non Ascii Font as a Ghostty fallback font-family; "
                "Ghostty cannot target only non-ASCII with this setting."
            )

    if profile.get("ASCII Ligatures") is False or profile.get("Non-ASCII Ligatures") is False:
        add_line(conv.config, "font-feature", "-calt, -liga, -dlig")
    disable_bold = profile.get("Use Bold Font") is False
    disable_italic = profile.get("Use Italic Font") is False
    if disable_bold:
        add_line(conv.config, "font-style-bold", "false")
    if disable_italic:
        add_line(conv.config, "font-style-italic", "false")
    if disable_bold or disable_italic:
        add_line(conv.config, "font-style-bold-italic", "false")

    h_spacing = profile.get("Horizontal Spacing")
    if isinstance(h_spacing, (int, float)) and h_spacing != 1:
        add_line(conv.config, "adjust-cell-width", f"{(h_spacing - 1) * 100:.2f}%")
    v_spacing = profile.get("Vertical Spacing")
    if isinstance(v_spacing, (int, float)) and v_spacing != 1:
        add_line(conv.config, "adjust-cell-height", f"{(v_spacing - 1) * 100:.2f}%")


def infer_job_title(profile: dict[str, Any]) -> str | None:
    """Best-effort title for iTerm2's JOB title component.

    iTerm2's default profile often uses only the JOB title component, which
    shows a login shell as "-zsh". Ghostty's native titlebar otherwise shows
    the working directory, so a static approximation is closer visually.
    """
    if profile.get("Custom Command") == "Yes" and profile.get("Command"):
        try:
            parts = shlex.split(str(profile["Command"]))
        except ValueError:
            parts = str(profile["Command"]).split()
        if parts:
            return Path(parts[0]).name
        return None

    shell = os.environ.get("SHELL")
    if shell:
        return f"-{Path(shell).name}"
    return None


def convert_window(profile: dict[str, Any], conv: Conversion) -> None:
    cols, rows = profile.get("Columns"), profile.get("Rows")
    if isinstance(cols, int) and isinstance(rows, int):
        add_line(conv.config, "window-width", cols)
        add_line(conv.config, "window-height", rows)

    transparency = profile.get("Transparency")
    use_transparency = profile.get("Initial Use Transparency", True)
    if isinstance(transparency, (int, float)) and use_transparency is not False:
        opacity = round(max(0, min(1, 1 - float(transparency))), 3)
        add_line(conv.config, "background-opacity", opacity)
        if profile.get("Only The Default BG Color Uses Transparency") is False:
            add_line(conv.config, "background-opacity-cells", "true")

    if profile.get("Blur"):
        radius = profile.get("Blur Radius")
        blur = int(radius) if isinstance(radius, (int, float)) and radius > 0 else "true"
        add_line(conv.config, "background-blur", blur)

    image = profile.get("Background Image Location")
    if image:
        add_line(conv.config, "background-image", image)
        mode = profile.get("Background Image Mode")
        # iTerm2: 0=stretch, 1=tile, 2=aspect-fill, 3=aspect-fit.
        fit = {0: "stretch", 1: "none", 2: "cover", 3: "contain"}.get(mode)
        if fit:
            add_line(conv.config, "background-image-fit", fit)
        if mode == 1:
            add_line(conv.config, "background-image-repeat", "true")
        blend = profile.get("Blend")
        if isinstance(blend, (int, float)):
            image_opacity = round(max(0, min(1, 1 - float(blend))), 3)
            add_line(conv.config, "background-image-opacity", image_opacity)

    window_type = profile.get("Window Type")
    if window_type in (1, "Fullscreen"):
        add_line(conv.config, "fullscreen", "true")

    if profile.get("Use Custom Window Title") and profile.get("Custom Window Title"):
        add_line(conv.config, "title", profile.get("Custom Window Title"))
    elif profile.get("Sync Title") and profile.get("Name"):
        add_line(conv.config, "title", profile.get("Name"))
    elif profile.get("Title Components") == 2:
        add_line(conv.config, "title", infer_job_title(profile))


def convert_terminal(profile: dict[str, Any], conv: Conversion) -> None:
    if profile.get("Custom Command") == "Yes" and profile.get("Command"):
        add_line(conv.config, "command", profile.get("Command"))

    custom_dir_mode = profile.get("Custom Directory")
    if custom_dir_mode == "Yes" and profile.get("Working Directory"):
        add_line(conv.config, "working-directory", profile.get("Working Directory"))
    elif custom_dir_mode == "No":
        add_line(conv.config, "working-directory", "home")
    elif custom_dir_mode == "Recycle":
        add_line(conv.config, "window-inherit-working-directory", "true")
        add_line(conv.config, "tab-inherit-working-directory", "true")
        add_line(conv.config, "split-inherit-working-directory", "true")

    scrollback = profile.get("Scrollback Lines")
    if profile.get("Unlimited Scrollback"):
        conv.warnings.append(
            "iTerm2 unlimited scrollback cannot be represented exactly; "
            "wrote a large Ghostty scrollback limit."
        )
        add_line(conv.config, "scrollback-limit", 4294967295)
    elif isinstance(scrollback, int) and scrollback >= 0:
        # Ghostty uses bytes, not lines. Estimate 160 bytes/line as a practical default.
        add_line(conv.config, "scrollback-limit", max(scrollback * 160, 1048576))
        conv.warnings.append(
            "Ghostty scrollback-limit is bytes, while iTerm2 stores lines; "
            "used an estimated 160 bytes per line."
        )

    if "Mouse Reporting" in profile:
        add_line(conv.config, "mouse-reporting", bool_text(profile.get("Mouse Reporting")))
    if "Allow Title Reporting" in profile:
        add_line(conv.config, "title-report", bool_text(profile.get("Allow Title Reporting")))
    if "Silence Bell" in profile and profile.get("Silence Bell"):
        add_line(conv.config, "bell-features", "no-system,no-audio,no-attention,no-title,no-border")
    elif profile.get("Send Bell Alert") or profile.get("BM Growl"):
        add_line(conv.config, "bell-features", "system,attention,title")

    if "Prompt Before Closing 2" in profile:
        confirm_close = bool_text(profile.get("Prompt Before Closing 2"))
        add_line(conv.config, "confirm-close-surface", confirm_close)
    if profile.get("Close Sessions On End") is False:
        add_line(conv.config, "wait-after-command", "true")
    if isinstance(profile.get("Session Close Undo Timeout"), (int, float)):
        add_line(conv.config, "undo-timeout", f"{profile.get('Session Close Undo Timeout')}s")

    if profile.get("Answerback String"):
        add_line(conv.config, "enquiry-response", profile.get("Answerback String"))


def convert_cursor_and_input(profile: dict[str, Any], conv: Conversion) -> None:
    if "Cursor Type" in profile:
        add_line(conv.config, "cursor-style", CURSOR_TYPES.get(profile.get("Cursor Type"), "block"))
    if "Blinking Cursor" in profile:
        add_line(conv.config, "cursor-style-blink", bool_text(profile.get("Blinking Cursor")))
    if isinstance(profile.get("Cursor Boost"), (int, float)):
        # iTerm2 boosts cursor contrast/visibility; Ghostty has opacity only. Keep fully visible.
        add_line(conv.config, "cursor-opacity", 1)
    minimum_contrast = profile.get("Minimum Contrast")
    if isinstance(minimum_contrast, (int, float)) and minimum_contrast > 0:
        # iTerm2 stores 0...1, Ghostty stores WCAG contrast ratio 1...21.
        add_line(conv.config, "minimum-contrast", round(1 + float(minimum_contrast) * 20, 2))

    left_alt = profile.get("Option Key Sends")
    right_alt = profile.get("Right Option Key Sends")
    if left_alt in OPTION_SENDS_ALT_VALUES and right_alt in OPTION_SENDS_ALT_VALUES:
        add_line(conv.config, "macos-option-as-alt", "true")
    elif left_alt in OPTION_SENDS_ALT_VALUES:
        add_line(conv.config, "macos-option-as-alt", "left")
    elif right_alt in OPTION_SENDS_ALT_VALUES:
        add_line(conv.config, "macos-option-as-alt", "right")

    if profile.get("Use libtickit protocol"):
        conv.warnings.append(
            "iTerm2 CSI-u/libtickit key protocol is not a one-to-one Ghostty "
            "setting; Ghostty enables modern keyboard protocols through "
            "TERM/terminal behavior."
        )

    shell_features = []
    # Ghostty's shell integration changes the cursor to a bar at the prompt.
    # iTerm2 keeps the profile cursor shape there, so disable just that part.
    if "Cursor Type" in profile:
        shell_features.append("no-cursor")
    # iTerm2's default title in a plain shell is usually the process name
    # (for example, "-zsh"). Ghostty otherwise changes it to the cwd.
    if profile.get("Sync Title") is False and not profile.get("Use Custom Window Title"):
        shell_features.append("no-title")
    if shell_features:
        add_line(conv.config, "shell-integration-features", ",".join(shell_features))


def convert_global_prefs(prefs: dict[str, Any], conv: Conversion) -> None:
    copy_on_select = prefs.get("Copy Selection")
    if isinstance(copy_on_select, bool):
        add_line(conv.config, "copy-on-select", bool_text(copy_on_select))
    if prefs.get("HideScrollbar") is True:
        add_line(conv.config, "scrollbar", "never")
    if prefs.get("QuitWhenAllWindowsClosed") is not None:
        quit_after_last_window = bool_text(prefs.get("QuitWhenAllWindowsClosed"))
        add_line(conv.config, "quit-after-last-window-closed", quit_after_last_window)

    # iTerm2's normal macOS window has a separate native titlebar. Ghostty's
    # default on macOS is transparent, which makes a dark terminal look quite
    # different. If iTerm2 is not drawing under the titlebar, prefer the native
    # Ghostty titlebar and let it stay light like iTerm2.
    if prefs.get("NSScrollViewShouldScrollUnderTitlebar") is False:
        add_line(conv.config, "macos-titlebar-style", "native")
        add_line(conv.config, "window-theme", "light")
    if prefs.get("EnableProxyIcon") is False:
        add_line(conv.config, "macos-titlebar-proxy-icon", "hidden")


def key_trigger(encoded: str) -> str | None:
    m = re.match(r"^0x([0-9a-fA-F]+)-0x([0-9a-fA-F]+)$", encoded)
    if not m:
        return None
    key_code = int(m.group(1), 16)
    modifiers = int(m.group(2), 16)
    key = SPECIAL_KEYS.get(key_code)
    if not key:
        try:
            char = chr(key_code)
        except (ValueError, OverflowError):
            return None
        if not char.isprintable() or char.isspace():
            return None
        key = char.lower()
        if modifiers & 0x20000:
            key = SHIFTED_US_KEYS.get(key, key)
    parts = [name for mask, name in MODIFIER_MASKS if modifiers & mask]
    parts.append(key)
    return "+".join(parts)


def zig_text_literal(text: str) -> str:
    # Convert iTerm2 hex byte lists ("0x1b 0x7f") or plain strings to Ghostty text: payload.
    if re.fullmatch(r"(?:0x[0-9a-fA-F]{1,2}\s*)+", text.strip()):
        chars = []
        for tok in text.split():
            chars.append(f"\\x{int(tok, 16):02x}")
        return "".join(chars)
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def convert_keymap(profile: dict[str, Any], conv: Conversion) -> None:
    keymap = profile.get("Keyboard Map")
    if not isinstance(keymap, dict):
        return
    converted = 0
    skipped = 0
    for encoded, binding in sorted(keymap.items()):
        if not isinstance(binding, dict):
            skipped += 1
            continue
        trigger = key_trigger(str(encoded))
        if not trigger:
            skipped += 1
            continue
        action = binding.get("Action")
        text = str(binding.get("Text", ""))
        if action == 10:  # Send escape sequence: ESC + text
            add_line(conv.config, "keybind", f"{trigger}=esc:{text}")
            converted += 1
        elif action == 11:  # Send text
            add_line(conv.config, "keybind", f"{trigger}=text:{zig_text_literal(text)}")
            converted += 1
        elif action == 12:  # Ignore
            add_line(conv.config, "keybind", f"{trigger}=ignore")
            converted += 1
        else:
            skipped += 1
    if converted:
        conv.warnings.append(
            f"Converted {converted} simple iTerm2 key mappings "
            "(send escape/text/ignore) to Ghostty keybind entries."
        )
    if skipped:
        conv.unsupported.append(
            f"Skipped {skipped} complex iTerm2 key mappings; "
            "inspect the iTerm2 Keyboard Map manually."
        )


def convert_profile(profile: dict[str, Any], prefs: dict[str, Any], color_mode: str) -> Conversion:
    conv = Conversion()
    name = profile.get("Name", "<unnamed>")
    conv.config.extend([
        "# Generated by iterm2_to_ghostty.py",
        f"# Source iTerm2 profile: {name}",
        "# Review warnings/comments before replacing an existing hand-written Ghostty config.",
        "",
    ])

    separate = bool(profile.get("Use Separate Colors for Light and Dark Mode"))
    if separate and color_mode == "auto":
        safe = safe_name(str(name))
        light_name = f"iterm2-{safe}-light"
        dark_name = f"iterm2-{safe}-dark"
        add_line(conv.config, "theme", f"light:{light_name},dark:{dark_name}")
        emit_theme(profile, conv.light_theme, "light")
        emit_theme(profile, conv.dark_theme, "dark")
    else:
        mode = color_mode if color_mode in ("light", "dark") else None
        emit_theme(profile, conv.config, mode)
        conv.config.append("")

    convert_font(profile, conv)
    convert_window(profile, conv)
    convert_terminal(profile, conv)
    convert_cursor_and_input(profile, conv)
    convert_global_prefs(prefs, conv)
    convert_keymap(profile, conv)

    for key, reason in UNSUPPORTED_PROFILE_KEYS.items():
        if key in profile and profile.get(key) not in (None, "", [], {}):
            conv.unsupported.append(f"{key}: {reason}")

    if conv.warnings:
        conv.config.extend(["", "# Conversion warnings:"])
        conv.config.extend(f"# - {w}" for w in conv.warnings)
    if conv.unsupported:
        conv.config.extend(["", "# iTerm2 settings not converted automatically:"])
        conv.config.extend(f"# - {u}" for u in conv.unsupported)
    conv.config.append("")
    return conv


def safe_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-.")
    return safe or "profile"


def write_outputs(
    conv: Conversion,
    out: Path,
    profile_name: str,
    dry_run: bool,
    backup: bool,
) -> None:
    config_text = "\n".join(conv.config)
    if dry_run:
        print(config_text)
        if conv.light_theme or conv.dark_theme:
            print("\n# --- light theme ---")
            print("\n".join(conv.light_theme))
            print("\n# --- dark theme ---")
            print("\n".join(conv.dark_theme))
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    if backup and out.exists():
        backup_path = (
            out.with_suffix(out.suffix + ".bak")
            if out.suffix
            else Path(str(out) + ".bak")
        )
        shutil.copy2(out, backup_path)
        print(f"Backed up existing Ghostty config to {backup_path}")
    out.write_text(config_text, encoding="utf-8")
    print(f"Wrote Ghostty config: {out}")

    if conv.light_theme or conv.dark_theme:
        themes_dir = out.parent / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        safe = safe_name(profile_name)
        if conv.light_theme:
            path = themes_dir / f"iterm2-{safe}-light"
            path.write_text("\n".join(conv.light_theme) + "\n", encoding="utf-8")
            print(f"Wrote Ghostty light theme: {path}")
        if conv.dark_theme:
            path = themes_dir / f"iterm2-{safe}-dark"
            path.write_text("\n".join(conv.dark_theme) + "\n", encoding="utf-8")
            print(f"Wrote Ghostty dark theme: {path}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert iTerm2 profile preferences to Ghostty config"
    )
    parser.add_argument(
        "--iterm-plist",
        type=Path,
        help="Path to com.googlecode.iterm2.plist or exported plist",
    )
    parser.add_argument(
        "--dynamic-profiles-dir",
        type=Path,
        help="Path to iTerm2 DynamicProfiles directory",
    )
    parser.add_argument(
        "--profile",
        help="iTerm2 profile name or Guid. Defaults to the iTerm2 default profile",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List discovered iTerm2 profiles and exit",
    )
    parser.add_argument(
        "--color-mode",
        choices=["auto", "single", "light", "dark"],
        default="auto",
        help="How to handle iTerm2 light/dark color variants",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_GHOSTTY_DIR / "config",
        help="Ghostty config output path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated config instead of writing files",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not back up an existing output file",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    prefs = load_iterm_preferences(args.iterm_plist)
    profiles = all_profiles(prefs, args.dynamic_profiles_dir)

    if args.list_profiles:
        default_guid = prefs.get("Default Bookmark Guid") or prefs.get("Default Bookmark GUID")
        for p in profiles:
            marker = "*" if p.get("Guid") == default_guid else " "
            source = p.get("__source", "preferences")
            print(f"{marker} {p.get('Name', '<unnamed>')}\t{p.get('Guid', '')}\t{source}")
        return 0

    profile = select_profile(profiles, prefs, args.profile)
    conv = convert_profile(profile, prefs, args.color_mode)
    write_outputs(
        conv,
        args.output,
        str(profile.get("Name", "profile")),
        args.dry_run,
        not args.no_backup,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
