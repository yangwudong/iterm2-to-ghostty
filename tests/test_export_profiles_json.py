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
