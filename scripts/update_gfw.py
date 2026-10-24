#!/usr/bin/env python3
import argparse
from pathlib import Path
from urllib.request import Request, urlopen

PRIMARY_URL = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release/gfw.txt"
FALLBACK_URL = "https://fastly.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/gfw.txt"

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shadowrocket"
TEMPLATE = ROOT / "shadowrocket_template.conf"

def fetch():
    last = None
    for url in (PRIMARY_URL, FALLBACK_URL):
        try:
            req = Request(url, headers={"User-Agent": "shadowrocket-gfw-sync/1.0"})
            with urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8")
            if "payload:" not in text:
                raise ValueError("unexpected upstream format")
            print("Downloaded:", url)
            return text
        except Exception as e:
            last = e
            print("Failed:", url, e)
    raise RuntimeError(last)

def parse(text):
    out, seen = [], set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s.startswith("-"):
            continue
        v = s[1:].strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
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

def write_rules(domains, output_dir=OUT, template_path=TEMPLATE):
    template = template_path.read_text(encoding="utf-8")
    marker = "# INSERT_GFW_RULES"
    if template.count(marker) != 1:
        raise ValueError("Configuration template must contain one GFW insertion marker")
    config = template.replace(
        marker,
        "# GFW domains: " + str(len(domains)) + "\n"
        + "\n".join("DOMAIN-SUFFIX," + d + ",PROXY" for d in domains),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/"gfw_domain_set.list").write_text(
        "\n".join("." + d for d in domains) + "\n", encoding="utf-8"
    )
    (output_dir/"gfw_rule_set.list").write_text(
        "\n".join("DOMAIN-SUFFIX," + d for d in domains) + "\n", encoding="utf-8"
    )
    (output_dir/"shadowrocket.conf").write_text(config, encoding="utf-8")
    print("Wrote", len(domains), "domains")


def main():
    parser = argparse.ArgumentParser(description="Build Shadowrocket rules and a complete configuration")
    parser.add_argument("--input", type=Path, help="Read a previously downloaded upstream list")
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8") if args.input else fetch()
    if not any(line.strip() == "payload:" for line in source.splitlines()):
        raise ValueError("Unexpected upstream format: missing payload")
    write_rules(parse(source))


if __name__ == "__main__":
    main()
