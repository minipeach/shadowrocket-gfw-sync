import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_gfw", ROOT / "scripts/update_gfw.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class ConversionTests(unittest.TestCase):
    def test_normalization_deduplication_and_invalid_entries(self):
        source = """payload:
  - '+.Example.COM'
  - '.example.com'
  - "Another.org."
  - 'invalid/path'
  - 'invalid domain'
"""
        self.assertEqual(update.parse(source), ["example.com", "another.org"])

    def test_empty_feed_is_rejected(self):
        with self.assertRaises(RuntimeError):
            update.parse("payload:\n")

    def test_standalone_config_and_override_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            update.write_rules(["schwab.com", "example.com"], output)
            config = (output / "shadowrocket.conf").read_text()
            self.assertIn("[General]", config)
            self.assertIn("[Rule]", config)
            self.assertLess(config.index("DOMAIN-SUFFIX,schwab.com,DIRECT"),
                            config.index("DOMAIN-SUFFIX,schwab.com,PROXY"))
            self.assertTrue(config.endswith("FINAL,DIRECT\n"))
            self.assertNotIn("# INSERT_GFW_RULES", config)
            self.assertNotIn("YOUR_GITHUB_NAME", config)
            self.assertNotIn("DOMAIN-SET,", config)
            self.assertEqual((output / "gfw_domain_set.list").read_text(),
                             ".schwab.com\n.example.com\n")
            self.assertEqual((output / "gfw_rule_set.list").read_text(),
                             "DOMAIN-SUFFIX,schwab.com\nDOMAIN-SUFFIX,example.com\n")

    def test_first_run_staged_diff_detects_new_files(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.run(["git", *args], cwd=directory, capture_output=True)
            self.assertEqual(git("init", "-q").returncode, 0)
            Path(directory, "shadowrocket.conf").write_text("[Rule]\nFINAL,DIRECT\n")
            self.assertEqual(git("diff", "--quiet").returncode, 0)
            self.assertEqual(git("add", "shadowrocket.conf").returncode, 0)
            self.assertEqual(git("diff", "--cached", "--quiet").returncode, 1)


if __name__ == "__main__":
    unittest.main()
