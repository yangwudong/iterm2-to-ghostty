# iterm2-to-ghostty

A small Python script for moving an iTerm2 profile into Ghostty.

It reads iTerm2's plist files, picks a profile, and writes a Ghostty config. The
conversion covers the stuff that maps reasonably well: colors, ANSI palette,
font, window size, opacity/blur, background images, cursor, command/working
directory, scrollback, mouse reporting, bell settings, close behavior, a few
global preferences, and simple key bindings.

Some iTerm2 features do not exist in Ghostty. Those are left as comments in the
output so you can decide what to do with them.

## Quick start

```bash
./iterm2_to_ghostty.py --list-profiles
./iterm2_to_ghostty.py --profile Default --dry-run
./iterm2_to_ghostty.py --profile Default
```

Default input paths:

- `~/Library/Preferences/com.googlecode.iterm2.plist`
- `~/Library/Application Support/iTerm2/DynamicProfiles/*`

Default output paths:

- `~/.config/ghostty/config`
- `~/.config/ghostty/themes/iterm2-*-light`
- `~/.config/ghostty/themes/iterm2-*-dark`

If `~/.config/ghostty/config` already exists, the script writes a `config.bak`
copy first. Use `--no-backup` if you do not want that.

## Options

```text
--iterm-plist PATH          read a copied/exported iTerm2 plist
--dynamic-profiles-dir DIR  read dynamic profiles from another directory
--profile NAME_OR_GUID      choose a profile; defaults to iTerm2's default
--color-mode MODE           auto, single, light, or dark
--output PATH               write a different Ghostty config file
--dry-run                   print the result instead of writing files
--iterm-keybinding-conventions
                            add extra iTerm2/macOS-style tab and split shortcuts
--no-backup                 skip the config.bak backup
```

## Tests

```bash
python3 -m unittest discover -s tests
python3 -m py_compile iterm2_to_ghostty.py
```
