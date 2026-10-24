import importlib.util
from ipaddress import ip_network
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
            networks = [ip_network("91.108.4.0/22"), ip_network("2001:b28:f23f::/48")]
            ads = ["DOMAIN-SUFFIX,ads.example.net", "IP-CIDR,203.0.113.0/24"]
            update.write_rules(["schwab.com", "example.com"], networks, ads, output)
            config = (output / "shadowrocket.conf").read_text()
            self.assertIn("[General]", config)
            self.assertIn("[Rule]", config)
            self.assertLess(config.index("DOMAIN-SUFFIX,schwab.com,DIRECT"),
                            config.index("DOMAIN-SUFFIX,schwab.com,PROXY"))
            self.assertTrue(config.endswith("FINAL,DIRECT\n"))
            self.assertNotIn("# INSERT_", config)
            for rule in ["IP-CIDR,91.108.4.0/22,PROXY,no-resolve",
                         "IP-CIDR6,2001:b28:f23f::/48,PROXY,no-resolve"]:
                self.assertIn(rule, config)
                self.assertLess(config.index(rule), config.index("GEOIP,CN,DIRECT"))
            self.assertNotIn("YOUR_GITHUB_NAME", config)
            self.assertNotIn("DOMAIN-SET,", config)
            ad_reference = "RULE-SET,https://minipeach.github.io/shadowrocket-gfw-sync/adblock_rule_set.list,REJECT"
            self.assertEqual(config.count(ad_reference), 1)
            self.assertLess(config.index("DOMAIN-SUFFIX,schwab.com,DIRECT"), config.index(ad_reference))
            self.assertLess(config.index(ad_reference), config.index("# Telegram IP ranges:"))
            self.assertLess(config.index(ad_reference), config.index("# GFW domains:"))
            self.assertNotIn("ads.example.net", config)
            ad_file = (output / "adblock_rule_set.list").read_text()
            self.assertIn("CC BY-SA 4.0", ad_file)
            self.assertEqual([line for line in ad_file.splitlines() if not line.startswith("#")], ads)
            self.assertEqual((output / "gfw_domain_set.list").read_text(),
                             ".schwab.com\n.example.com\n")
            self.assertEqual((output / "gfw_rule_set.list").read_text(),
                             "DOMAIN-SUFFIX,schwab.com\nDOMAIN-SUFFIX,example.com\n")
            self.assertEqual((output / "telegramcidr_rule_set.list").read_text(),
                             "IP-CIDR,91.108.4.0/22,no-resolve\n"
                             "IP-CIDR6,2001:b28:f23f::/48,no-resolve\n")

    def test_telegram_ipv4_ipv6_normalization_and_deduplication(self):
        source = """payload:
  - '91.108.4.0/22'
  - '91.108.4.1/22'
  - "2001:B28:F23F::/48"
  - '2001:b28:f23f:0::/48'
"""
        self.assertEqual([str(n) for n in update.parse_telegram(source)],
                         ["91.108.4.0/22", "2001:b28:f23f::/48"])

    def test_invalid_or_empty_telegram_feeds_are_rejected(self):
        for source in ["<html>Error</html>", "payload:\n", "payload:\n - 'example.com'",
                       "payload:\n - '91.108.4.0/33'", "payload:\n - '2001:b28::/129'"]:
            with self.subTest(source=source), self.assertRaises((ValueError, RuntimeError)):
                update.parse_telegram(source)

    def test_fetch_falls_back_on_download_or_validation_failure(self):
        valid = MagicMock()
        valid.__enter__.return_value.read.return_value = b"payload:\n - '91.108.4.0/22'\n"
        invalid = MagicMock()
        invalid.__enter__.return_value.read.return_value = b"payload:\n - 'invalid-cidr'\n"
        for first in [OSError("unavailable"), invalid]:
            with self.subTest(first=type(first).__name__), patch.object(
                update, "urlopen", side_effect=[first, valid]
            ) as mocked:
                result = update.fetch(update.TELEGRAM_PRIMARY_URL, update.TELEGRAM_FALLBACK_URL,
                                      update.parse_telegram)
                self.assertEqual([str(n) for n in result], ["91.108.4.0/22"])
                self.assertEqual(mocked.call_args_list[1].args[0].full_url,
                                 update.TELEGRAM_FALLBACK_URL)

    def test_failed_telegram_download_does_not_write_partial_outputs(self):
        with patch("sys.argv", ["update_gfw.py"]), patch.object(
            update, "fetch", side_effect=[["example.com"], RuntimeError("Telegram unavailable")]
        ), patch.object(update, "write_rules") as write:
            with self.assertRaises(RuntimeError):
                update.main()
            write.assert_not_called()

    def test_ad_rules_extract_only_rule_section_and_remove_policies(self):
        source = """[General]
ipv6 = false
[Rule]
# An ad domain and duplicated IP ranges
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

    def test_failed_ad_download_does_not_write_partial_outputs(self):
        with patch("sys.argv", ["update_gfw.py"]), patch.object(
            update, "fetch", side_effect=[["example.com"], [ip_network("91.108.4.0/22")],
                                         RuntimeError("Ad source unavailable")]
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
