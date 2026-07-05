import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from iterm2_to_ghostty import slugify_id, detect_type, build_profiles_document


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

    def test_skips_port_flag_value(self):
        self.assertEqual(
            ssh_tokens("ssh -p 2222 jack@host.example.com"),
            ["jack", "host", "example", "com"],
        )


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

    def test_shell_without_custom_dir_drops_stale_working_directory(self):
        bm = {
            "Name": "Stale Shell",
            "Custom Command": "No",
            "Command": "cd",
            "Custom Directory": "No",
            "Working Directory": "/Users/jack/should-be-ignored",
        }
        result = normalize_profile(bm)
        self.assertIsNone(result["working_directory"])

    def test_command_profile_keeps_command_and_working_directory(self):
        bm = {
            "Name": "Builder",
            "Custom Command": "Yes",
            "Command": "docker compose up",
            "Custom Directory": "Yes",
            "Working Directory": "/Users/jack/work/build",
        }
        result = normalize_profile(bm)
        self.assertEqual(result["type"], "command")
        self.assertEqual(result["command"], "docker compose up")
        self.assertEqual(result["working_directory"], "/Users/jack/work/build")



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


if __name__ == "__main__":
    unittest.main()
