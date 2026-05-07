# Mapping notes

These are the iTerm2 settings the script currently knows about. The source of
truth for Ghostty options is the Ghostty config reference. For iTerm2 plist keys,
the most useful reference was iTerm2's Python API profile schema
(`api/library/python/iterm2/gen_profile.py`), because it names the actual plist
keys.

## Inputs

- Main preferences: `~/Library/Preferences/com.googlecode.iterm2.plist`
- Fallback when the plist is not present: `defaults export com.googlecode.iterm2 -`
- Dynamic profiles: `~/Library/Application Support/iTerm2/DynamicProfiles/*`

Dynamic profiles with a matching `Guid` are merged on top of the base profile,
which is how iTerm2 treats sparse dynamic profiles.

## Outputs

- Ghostty config: `~/.config/ghostty/config`
- Optional Ghostty themes: `~/.config/ghostty/themes/iterm2-<profile>-light`
  and `iterm2-<profile>-dark`

## Mapped settings

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
| `ASCII Ligatures` / `Non-ASCII Ligatures` false | `font-feature` disabling common ligature features |
| `Use Bold Font` false | `font-style-bold = false` |
| `Use Italic Font` false | `font-style-italic = false` |
| `Horizontal Spacing` / `Vertical Spacing` | `adjust-cell-width` / `adjust-cell-height` |
| `Columns` / `Rows` | `window-width` / `window-height` |
| `Transparency` | `background-opacity = 1 - transparency` |
| `Only The Default BG Color Uses Transparency` false | `background-opacity-cells = true` |
| `Blur` / `Blur Radius` | `background-blur` |
| `Background Image Location` | `background-image` |
| `Background Image Mode` | `background-image-fit`; tile also sets repeat |
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
| `Cursor Type` | `cursor-style`, plus `shell-integration-features = no-cursor` so Ghostty does not force a bar cursor at prompts |
| `Blinking Cursor` | `cursor-style-blink` |
| `Minimum Contrast` | `minimum-contrast`, scaled from 0–1 to 1–21 |
| `Option Key Sends`, `Right Option Key Sends` | `macos-option-as-alt` |
| simple `Keyboard Map` entries | `keybind` |
| `Title Components` set to job only | static `title` based on the shell or custom command |
| `Sync Title` false | `shell-integration-features = no-title` |

## Global preferences

| iTerm2 preference | Ghostty key |
|---|---|
| `Copy Selection` | `copy-on-select` |
| `HideScrollbar` | `scrollbar = never` |
| `QuitWhenAllWindowsClosed` | `quit-after-last-window-closed` |
| `NSScrollViewShouldScrollUnderTitlebar` false | `macos-titlebar-style = native`, `window-theme = light` |
| `EnableProxyIcon` false | `macos-titlebar-proxy-icon = hidden` |

## Known gaps

The script does not try to fake iTerm2-only features. It reports them in the
generated config instead. Common examples are triggers/coprocesses, smart
selection actions, semantic history, automatic profile switching, badges, the
status bar, legacy character encodings, unicode normalization, and complex key
actions.
