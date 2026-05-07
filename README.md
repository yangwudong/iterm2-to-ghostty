# iTerm2 to Ghostty converter

`iterm2_to_ghostty.py` converts an iTerm2 profile plist into a Ghostty config. It focuses on settings Ghostty can represent: colors, ANSI palette, font, size, opacity/blur, background image, cursor, shell/working directory, scrollback, mouse reporting, bell behavior, close behavior, selected global preferences, and simple key mappings.

## Usage

```bash
./iterm2_to_ghostty.py --list-profiles
./iterm2_to_ghostty.py --profile Default --dry-run
./iterm2_to_ghostty.py --profile Default
```

By default it reads:

- `~/Library/Preferences/com.googlecode.iterm2.plist`
- `~/Library/Application Support/iTerm2/DynamicProfiles/*`

and writes:

- `~/.config/ghostty/config`
- `~/.config/ghostty/themes/iterm2-*-light` / `iterm2-*-dark` when the iTerm2 profile uses separate light/dark colors.

Existing Ghostty config files are backed up to `config.bak` unless `--no-backup` is passed.

## Useful options

```bash
--iterm-plist PATH          Read an exported or copied iTerm2 plist
--dynamic-profiles-dir DIR  Read dynamic profiles from a custom directory
--profile NAME_OR_GUID      Choose an iTerm2 profile
--color-mode auto|single|light|dark
--output PATH               Write a custom Ghostty config path
--dry-run                   Print instead of writing files
--no-backup                 Do not back up an existing output file
```

## Notes

Some iTerm2 features have no direct Ghostty equivalent. The generated config includes comments for skipped or approximate settings so you can review them manually. Simple iTerm2 key mappings for “send escape sequence”, “send text”, and “ignore” are converted to Ghostty `keybind` entries; more complex actions are reported as skipped.

## Development

```bash
python3 -m unittest discover -s tests
python3 -m py_compile iterm2_to_ghostty.py
```
