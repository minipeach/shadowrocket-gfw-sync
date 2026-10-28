#!/usr/bin/env python3
import argparse
from ipaddress import ip_network
from pathlib import Path
from urllib.request import Request, urlopen

AD_PRIMARY_URL = "https://johnshall.github.io/Shadowrocket-ADBlock-Rules-Forever/sr_ad_only.conf"
AD_FALLBACK_URL = "https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_ad_only.conf"

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shadowrocket"
TEMPLATE = ROOT / "shadowrocket_template.conf"

def fetch(primary_url, fallback_url, parser):
    last = None
    for url in (primary_url, fallback_url):
        try:
            req = Request(url, headers={"User-Agent": "shadowrocket-gfw-sync/1.0"})
            with urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8")
            parsed = parser(text)
            print("Downloaded:", url)
            return parsed
        except Exception as e:
            last = e
            print("Failed:", url, e)
    raise RuntimeError(last)

def parse_ad_rules(text):
    section = ""
    rules, seen = [], set()
    domain_types = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            continue
        if section != "[rule]":
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) not in (3, 4) or parts[2].upper() != "REJECT":
            raise ValueError("Unexpected ad rule or policy: " + line)
        kind, value = parts[0].upper(), parts[1]
        if not value or any(char.isspace() for char in value):
            raise ValueError("Invalid ad rule value: " + line)
        options = parts[3:]
        if options and options != ["no-resolve"]:
            raise ValueError("Unsupported ad rule option: " + line)
        if kind in domain_types:
            value = value.lower()
        elif kind in ("IP-CIDR", "IP-CIDR6"):
            network = ip_network(value, strict=False)
            kind = "IP-CIDR6" if network.version == 6 else "IP-CIDR"
            value = str(network)
        else:
            raise ValueError("Unsupported ad rule type: " + kind)
        rule = ",".join([kind, value] + options)
        if rule not in seen:
            seen.add(rule)
            rules.append(rule)
    if not rules:
        raise RuntimeError("No ad blocking rules parsed; upstream format may have changed.")
    return rules


def write_rules(ad_rules, output_dir=OUT, template_path=TEMPLATE):
    config = template_path.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/"adblock_rule_set.list").write_text(
        "# Derived from Johnshall/Shadowrocket-ADBlock-Rules-Forever (Moshel and Johnshall)\n"
        "# Source: " + AD_PRIMARY_URL + "\n"
        "# License: CC BY-SA 4.0 https://creativecommons.org/licenses/by-sa/4.0/\n"
        "# Modified: extracted REJECT rules, removed policies, canonicalized CIDRs, deduplicated.\n"
        + "\n".join(ad_rules) + "\n", encoding="utf-8"
    )
    (output_dir/"shadowrocket.conf").write_text(config, encoding="utf-8")
    print("Wrote personal configuration and", len(ad_rules), "external ad blocking rules")


def main():
    parser = argparse.ArgumentParser(description="Publish personal Shadowrocket configuration and convert ad rules")
    parser.add_argument("--ad-input", type=Path, help="Read a previously downloaded Johnshall ad configuration")
    args = parser.parse_args()
    ad_rules = parse_ad_rules(args.ad_input.read_text(encoding="utf-8")) if args.ad_input else fetch(
        AD_PRIMARY_URL, AD_FALLBACK_URL, parse_ad_rules
    )
    write_rules(ad_rules)


if __name__ == "__main__":
    main()
