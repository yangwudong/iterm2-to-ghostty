# iTerm2 → Ghostty mapping notes

Research sources used:

- Ghostty configuration reference: `https://ghostty.org/docs/config/reference`
- iTerm2 profile preference docs: General, Text, Colors, Terminal, Window, Keys
- iTerm2 Dynamic Profiles docs
- iTerm2 Python API profile schema (`api/library/python/iterm2/gen_profile.py`), which exposes actual plist key names.

## Files read by the converter

- Main iTerm2 preferences: `~/Library/Preferences/com.googlecode.iterm2.plist`
- Fallback main preferences export: `defaults export com.googlecode.iterm2 -`
- Dynamic profiles: `~/Library/Application Support/iTerm2/DynamicProfiles/*`

Dynamic profiles are merged over base preference profiles with the same `Guid`, matching iTerm2's overlay behavior.

## Files written by the converter

- Ghostty config: `~/.config/ghostty/config` by default
- Ghostty themes: `~/.config/ghostty/themes/iterm2-<profile>-light` and `...-dark` when iTerm2 separate light/dark colors are enabled.

## Direct/near-direct mappings

| iTerm2 plist key | Ghostty key |
|---|---|
| `Foreground Color` | `foreground` |
| `Background Color` | `background` |
| `Bold Color` + `Use Bright Bold` | `bold-color` |
| `Cursor Color` | `cursor-color` |
| `Cursor Text Color` | `cursor-text` |
| `Selection Color` | `selection-background` |
| `Selected Text Color` | `selection-foreground` |
| `Ansi 0 Color` … `Ansi 15 Color` | `palette = 0=...` … `15=...` |
| `Normal Font` | `font-family`, `font-size` |
| `Non Ascii Font` | extra `font-family` fallback |
| `ASCII Ligatures` / `Non-ASCII Ligatures` false | `font-feature = "-calt, -liga, -dlig"` |
| `Use Bold Font` false | `font-style-bold = false` |
| `Use Italic Font` false | `font-style-italic = false` |
| `Horizontal Spacing` / `Vertical Spacing` | `adjust-cell-width` / `adjust-cell-height` percentage adjustment |
| `Columns` / `Rows` | `window-width` / `window-height` |
| `Transparency` | `background-opacity = 1 - transparency` |
| `Only The Default BG Color Uses Transparency` false | `background-opacity-cells = true` |
| `Blur` / `Blur Radius` | `background-blur` |
| `Background Image Location` | `background-image` |
| `Background Image Mode` | `background-image-fit`; tiled mode also sets `background-image-repeat = true` |
| `Blend` | approximate `background-image-opacity` |
| `Window Type` fullscreen | `fullscreen = true` |
| `Use Custom Window Title` / `Custom Window Title` | `title` |
| `Custom Command` / `Command` | `command` |
| `Custom Directory` / `Working Directory` | `working-directory`, inheritance keys |
| `Scrollback Lines` | estimated `scrollback-limit` in bytes |
| `Unlimited Scrollback` | large `scrollback-limit` |
| `Mouse Reporting` | `mouse-reporting` |
| `Allow Title Reporting` | `title-report` |
| `Silence Bell` / bell alerts | `bell-features` |
| `Prompt Before Closing 2` | `confirm-close-surface` |
| `Close Sessions On End` false | `wait-after-command = true` |
| `Session Close Undo Timeout` | `undo-timeout` |
| `Answerback String` | `enquiry-response` |
| `Cursor Type` | `cursor-style` |
| `Blinking Cursor` | `cursor-style-blink` |
| `Minimum Contrast` | `minimum-contrast` scaled from 0–1 to 1–21 |
| `Option Key Sends`, `Right Option Key Sends` | `macos-option-as-alt` |
| simple `Keyboard Map` entries | `keybind` |

## Global preferences mapped when present

| iTerm2 preference | Ghostty key |
|---|---|
| `Copy Selection` | `copy-on-select` |
| `HideScrollbar` | `scrollbar = never` |
| `QuitWhenAllWindowsClosed` | `quit-after-last-window-closed` |

## Not automatically representable

The generated config comments list any encountered keys that are not converted. Common examples: iTerm2 triggers/coprocesses, smart selection actions, semantic history, automatic profile switching, badges, status bar, legacy character encodings, unicode normalization, and some complex key actions.
