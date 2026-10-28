import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_gfw", ROOT / "scripts/update_gfw.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class ConversionTests(unittest.TestCase):
    def test_config_preserves_personal_settings_and_remote_rule_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            ads = ["DOMAIN-SUFFIX,ads.example.net", "IP-CIDR,203.0.113.0/24"]
            update.write_rules(ads, output)
            config = (output / "shadowrocket.conf").read_text()
            self.assertEqual(config, update.TEMPLATE.read_text())
            base = "RULE-SET,https://fastly.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/ruleset/"
            telegram = base + "telegramcidr.txt,PROXY,no-resolve"
            gfw = base + "gfw.txt,PROXY"
            ad_reference = "RULE-SET,https://minipeach.github.io/shadowrocket-gfw-sync/adblock_rule_set.list,REJECT"
            sequence = ["DOMAIN-SUFFIX,schwab.com,DIRECT", ad_reference, telegram, gfw,
                        "GEOIP,CN,DIRECT", "FINAL,DIRECT", "[URL Rewrite]", "[MITM]"]
            positions = [config.index(rule) for rule in sequence]
            self.assertEqual(positions, sorted(positions))
            for rule in [ad_reference, telegram, gfw]:
                self.assertEqual(config.count(rule), 1)
            self.assertNotIn("# INSERT_", config)
            self.assertNotIn("ads.example.net", config)
            self.assertNotIn("DOMAIN-SUFFIX,000webhost.com,PROXY", config)
            self.assertEqual({p.name for p in output.iterdir()},
                             {"shadowrocket.conf", "adblock_rule_set.list"})
            ad_file = (output / "adblock_rule_set.list").read_text()
            self.assertIn("CC BY-SA 4.0", ad_file)
            self.assertEqual([line for line in ad_file.splitlines() if not line.startswith("#")], ads)

    def test_ad_rules_extract_only_rule_section_and_remove_policies(self):
        source = """[General]
ipv6 = false
[Rule]
DOMAIN-SUFFIX,Ads.Example.net,Reject
DOMAIN-SUFFIX,ads.example.net,REJECT
IP-CIDR,203.0.113.5/24,Reject,no-resolve
IP-CIDR,203.0.113.0/24,Reject,no-resolve
IP-CIDR6,2001:DB8::/32,Reject
[URL Rewrite]
^https://example.net https://example.org 302
[MITM]
hostname = *.example.net
"""
        self.assertEqual(update.parse_ad_rules(source), [
            "DOMAIN-SUFFIX,ads.example.net", "IP-CIDR,203.0.113.0/24,no-resolve",
            "IP-CIDR6,2001:db8::/32",
        ])

    def test_ad_rules_reject_empty_malformed_or_unsafe_feeds(self):
        for source in ["<html>Error</html>", "[Rule]\n", "[Rule]\nFINAL,REJECT",
                       "[Rule]\nDOMAIN-SUFFIX,example.net,DIRECT",
                       "[Rule]\nDOMAIN-SUFFIX,example.net,REJECT,unsupported",
                       "[Rule]\nRULE-SET,https://example.net/list,REJECT",
                       "[Rule]\nIP-CIDR,not-an-ip,REJECT"]:
            with self.subTest(source=source), self.assertRaises((ValueError, RuntimeError)):
                update.parse_ad_rules(source)

    def test_fetch_falls_back_on_download_or_validation_failure(self):
        valid = MagicMock()
        valid.__enter__.return_value.read.return_value = b"[Rule]\nDOMAIN-SUFFIX,ads.example.net,REJECT\n"
        invalid = MagicMock()
        invalid.__enter__.return_value.read.return_value = b"[Rule]\nFINAL,DIRECT\n"
        for first in [OSError("unavailable"), invalid]:
            with self.subTest(first=type(first).__name__), patch.object(
                update, "urlopen", side_effect=[first, valid]
            ) as mocked:
                result = update.fetch(update.AD_PRIMARY_URL, update.AD_FALLBACK_URL, update.parse_ad_rules)
                self.assertEqual(result, ["DOMAIN-SUFFIX,ads.example.net"])
                self.assertEqual(mocked.call_args_list[1].args[0].full_url, update.AD_FALLBACK_URL)

    def test_main_only_downloads_ads(self):
        ads = ["DOMAIN-SUFFIX,ads.example.net"]
        with patch("sys.argv", ["update_gfw.py"]), patch.object(update, "fetch", return_value=ads) as fetch, patch.object(update, "write_rules") as write:
            update.main()
            fetch.assert_called_once_with(update.AD_PRIMARY_URL, update.AD_FALLBACK_URL, update.parse_ad_rules)
            write.assert_called_once_with(ads)

    def test_failed_ad_download_does_not_write_partial_outputs(self):
        with patch("sys.argv", ["update_gfw.py"]), patch.object(
            update, "fetch", side_effect=RuntimeError("Ad source unavailable")
        ), patch.object(update, "write_rules") as write:
            with self.assertRaises(RuntimeError):
                update.main()
            write.assert_not_called()

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
