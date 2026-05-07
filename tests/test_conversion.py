import tempfile
import unittest
from pathlib import Path

import plistlib

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iterm2_to_ghostty import (
    all_profiles,
    convert_profile,
    infer_job_title,
    key_trigger,
    ghostty_font_family,
    load_iterm_preferences,
)


class ConversionTests(unittest.TestCase):
    def test_postscript_font_name_maps_to_ghostty_family(self):
        self.assertEqual(ghostty_font_family("SFMono-Regular"), "SF Mono")
        self.assertEqual(ghostty_font_family("Menlo-Regular"), "Menlo")
        self.assertEqual(ghostty_font_family("Monaco"), "Monaco")

    def test_dynamic_profile_overlays_base_profile_by_guid(self):
        prefs = {
            "New Bookmarks": [
                {
                    "Name": "Base",
                    "Guid": "G",
                    "Normal Font": "Menlo 12",
                    "Background Color": {
                        "Red Component": 0,
                        "Green Component": 0,
                        "Blue Component": 0,
                    },
                }
            ],
            "Default Bookmark Guid": "G",
        }
        with tempfile.TemporaryDirectory() as tmp:
            dynamic_dir = Path(tmp)
            dynamic_profile = {
                "Profiles": [
                    {"Name": "Overlay", "Guid": "G", "Columns": 100, "Rows": 30}
                ]
            }
            (dynamic_dir / "profile.plist").write_bytes(plistlib.dumps(dynamic_profile))
            profiles = all_profiles(prefs, dynamic_dir)

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["Name"], "Overlay")
        self.assertEqual(profiles[0]["Normal Font"], "Menlo 12")
        self.assertEqual(profiles[0]["Columns"], 100)

    def test_background_tile_maps_to_repeat(self):
        profile = {
            "Name": "Image",
            "Guid": "G",
            "Background Image Location": "/tmp/bg.png",
            "Background Image Mode": 1,
        }
        text = "\n".join(convert_profile(profile, {}, "single").config)
        self.assertIn("background-image-fit = none", text)
        self.assertIn("background-image-repeat = true", text)

    def test_close_sessions_on_end_false_maps_to_wait_after_command(self):
        profile = {"Name": "Keep", "Guid": "G", "Close Sessions On End": False}
        text = "\n".join(convert_profile(profile, {}, "single").config)
        self.assertIn("wait-after-command = true", text)

    def test_color_output_is_bare_hex(self):
        profile = {
            "Name": "Color",
            "Guid": "G",
            "Background Color": {
                "Red Component": 1,
                "Green Component": 0.5,
                "Blue Component": 0,
            },
        }
        text = "\n".join(convert_profile(profile, {}, "single").config)
        self.assertIn("background = ff8000", text)
        self.assertNotIn('background = "#ff8000"', text)

    def test_shifted_printable_key_trigger_uses_base_key(self):
        self.assertEqual(key_trigger("0x5e-0x60000"), "ctrl+shift+6")

    def test_job_title_component_sets_static_shell_title(self):
        profile = {"Name": "P", "Guid": "G", "Title Components": 2}
        text = "\n".join(convert_profile(profile, {}, "single").config)
        self.assertRegex(text, r"(?m)^title = -\w+", msg=text)

    def test_custom_command_job_title_uses_command_name(self):
        profile = {"Custom Command": "Yes", "Command": "/usr/bin/top -u"}
        self.assertEqual(infer_job_title(profile), "top")

    def test_native_iterm_titlebar_maps_to_native_ghostty_titlebar(self):
        prefs = {
            "NSScrollViewShouldScrollUnderTitlebar": False,
            "EnableProxyIcon": False,
        }
        text = "\n".join(convert_profile({"Name": "P", "Guid": "G"}, prefs, "single").config)
        self.assertIn("macos-titlebar-style = native", text)
        self.assertIn("window-theme = light", text)
        self.assertIn("macos-titlebar-proxy-icon = hidden", text)

    def test_iterm_cursor_shape_disables_ghostty_prompt_cursor_override(self):
        profile = {"Name": "P", "Guid": "G", "Cursor Type": 0}
        text = "\n".join(convert_profile(profile, {}, "single").config)
        self.assertIn("cursor-style = underline", text)
        self.assertIn("shell-integration-features = no-cursor", text)

    def test_unsynced_iterm_title_disables_ghostty_shell_title(self):
        profile = {"Name": "P", "Guid": "G", "Cursor Type": 0, "Sync Title": False}
        text = "\n".join(convert_profile(profile, {}, "single").config)
        self.assertIn("shell-integration-features = no-cursor,no-title", text)

    def test_load_iterm_preferences_from_explicit_path(self):
        prefs = {"New Bookmarks": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prefs.plist"
            path.write_bytes(plistlib.dumps(prefs))
            self.assertEqual(load_iterm_preferences(path), prefs)


if __name__ == "__main__":
    unittest.main()
