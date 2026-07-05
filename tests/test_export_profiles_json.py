import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iterm2_to_ghostty import slugify_id, detect_type


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


if __name__ == "__main__":
    unittest.main()
