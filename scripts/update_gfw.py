#!/usr/bin/env python3
import argparse
from ipaddress import ip_network
from pathlib import Path
from urllib.request import Request, urlopen

PRIMARY_URL = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/gfw.txt"
FALLBACK_URL = "https://fastly.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/gfw.txt"
TELEGRAM_PRIMARY_URL = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/telegramcidr.txt"
TELEGRAM_FALLBACK_URL = "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/telegramcidr.txt"

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


def write_rules(domains, telegram_cidrs, output_dir=OUT, template_path=TEMPLATE):
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
    (output_dir/"shadowrocket.conf").write_text(config, encoding="utf-8")
    print("Wrote", len(domains), "domains and", len(telegram_cidrs), "Telegram IP ranges")


def main():
    parser = argparse.ArgumentParser(description="Build Shadowrocket rules and a complete configuration")
    parser.add_argument("--input", type=Path, help="Read a previously downloaded upstream list")
    parser.add_argument("--telegram-input", type=Path, help="Read a previously downloaded Telegram CIDR list")
    args = parser.parse_args()
    domains = parse(args.input.read_text(encoding="utf-8")) if args.input else fetch(
        PRIMARY_URL, FALLBACK_URL, parse
    )
    telegram_cidrs = parse_telegram(args.telegram_input.read_text(encoding="utf-8")) if args.telegram_input else fetch(
        TELEGRAM_PRIMARY_URL, TELEGRAM_FALLBACK_URL, parse_telegram
    )
    write_rules(domains, telegram_cidrs)


if __name__ == "__main__":
    main()
