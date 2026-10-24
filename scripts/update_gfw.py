#!/usr/bin/env python3
import argparse
from ipaddress import ip_network
from pathlib import Path
from urllib.request import Request, urlopen

PRIMARY_URL = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/gfw.txt"
FALLBACK_URL = "https://fastly.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/gfw.txt"
TELEGRAM_PRIMARY_URL = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/telegramcidr.txt"
TELEGRAM_FALLBACK_URL = "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/telegramcidr.txt"
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

def payload_values(text):
    if not any(line.strip() == "payload:" for line in text.splitlines()):
        raise ValueError("Unexpected upstream format: missing payload")
    for raw in text.splitlines():
        s = raw.strip()
        if not s.startswith("-"):
            continue
        v = s[1:].strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        yield v


def parse(text):
    out, seen = [], set()
    for v in payload_values(text):
        if v.startswith("+."):
            v = v[2:]
        elif v.startswith("."):
            v = v[1:]
        v = v.strip().lower().rstrip(".")
        if not v or "/" in v or any(c.isspace() for c in v):
            continue
        if v not in seen:
            seen.add(v)
            out.append(v)
    if not out:
        raise RuntimeError("No domains parsed; upstream format may have changed.")
    return out


def parse_telegram(text):
    out, seen = [], set()
    for value in payload_values(text):
        if "/" not in value:
            raise ValueError("Telegram entry is not a CIDR: " + value)
        network = ip_network(value, strict=False)
        if network not in seen:
            seen.add(network)
            out.append(network)
    if not out:
        raise RuntimeError("No Telegram CIDRs parsed; upstream format may have changed.")
    return out


def telegram_rule(network, policy=None):
    parts = ["IP-CIDR6" if network.version == 6 else "IP-CIDR", str(network)]
    if policy:
        parts.append(policy)
    parts.append("no-resolve")
    return ",".join(parts)


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


def write_rules(domains, telegram_cidrs, ad_rules, output_dir=OUT, template_path=TEMPLATE):
    template = template_path.read_text(encoding="utf-8")
    sections = {
        "# INSERT_GFW_RULES": "# GFW domains: " + str(len(domains)) + "\n"
        + "\n".join("DOMAIN-SUFFIX," + d + ",PROXY" for d in domains),
        "# INSERT_TELEGRAM_RULES": "# Telegram IP ranges: " + str(len(telegram_cidrs)) + "\n"
        + "\n".join(telegram_rule(n, "PROXY") for n in telegram_cidrs),
    }
    config = template
    for marker, content in sections.items():
        if template.count(marker) != 1:
            raise ValueError("Configuration template must contain exactly one " + marker)
        config = config.replace(marker, content)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/"gfw_domain_set.list").write_text(
        "\n".join("." + d for d in domains) + "\n", encoding="utf-8"
    )
    (output_dir/"gfw_rule_set.list").write_text(
        "\n".join("DOMAIN-SUFFIX," + d for d in domains) + "\n", encoding="utf-8"
    )
    (output_dir/"telegramcidr_rule_set.list").write_text(
        "\n".join(telegram_rule(n) for n in telegram_cidrs) + "\n", encoding="utf-8"
    )
    (output_dir/"adblock_rule_set.list").write_text(
        "# Derived from Johnshall/Shadowrocket-ADBlock-Rules-Forever (Moshel and Johnshall)\n"
        "# Source: " + AD_PRIMARY_URL + "\n"
        "# License: CC BY-SA 4.0 https://creativecommons.org/licenses/by-sa/4.0/\n"
        "# Modified: extracted REJECT rules, removed policies, canonicalized CIDRs, deduplicated.\n"
        + "\n".join(ad_rules) + "\n", encoding="utf-8"
    )
    (output_dir/"shadowrocket.conf").write_text(config, encoding="utf-8")
    print("Wrote", len(domains), "domains,", len(telegram_cidrs), "Telegram IP ranges and",
          len(ad_rules), "external ad blocking rules")


def main():
    parser = argparse.ArgumentParser(description="Build Shadowrocket rules and a complete configuration")
    parser.add_argument("--input", type=Path, help="Read a previously downloaded upstream list")
    parser.add_argument("--telegram-input", type=Path, help="Read a previously downloaded Telegram CIDR list")
    parser.add_argument("--ad-input", type=Path, help="Read a previously downloaded Johnshall ad configuration")
    args = parser.parse_args()
    domains = parse(args.input.read_text(encoding="utf-8")) if args.input else fetch(
        PRIMARY_URL, FALLBACK_URL, parse
    )
    telegram_cidrs = parse_telegram(args.telegram_input.read_text(encoding="utf-8")) if args.telegram_input else fetch(
        TELEGRAM_PRIMARY_URL, TELEGRAM_FALLBACK_URL, parse_telegram
    )
    ad_rules = parse_ad_rules(args.ad_input.read_text(encoding="utf-8")) if args.ad_input else fetch(
        AD_PRIMARY_URL, AD_FALLBACK_URL, parse_ad_rules
    )
    write_rules(domains, telegram_cidrs, ad_rules)


if __name__ == "__main__":
    main()
