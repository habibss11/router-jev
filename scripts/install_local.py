#!/usr/bin/env python3
"""Register this local marketplace and install its plugin through Codex CLI."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_ROOT = ROOT.parent
CATALOG = MARKETPLACE_ROOT / ".agents/plugins/marketplace.json"


def main():
    entry = json.loads((ROOT / "installation/marketplace.json").read_text())
    if CATALOG.exists():
        existing = json.loads(CATALOG.read_text())
        if existing.get("name") != entry["name"]:
            print("Existing marketplace has another name; no files changed.", file=sys.stderr)
            return 1
        plugins = existing.setdefault("plugins", [])
        plugins[:] = [p for p in plugins if p.get("name") != "jev-codex-router"]
        plugins.append(entry["plugins"][0])
        entry = existing
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
    subprocess.run([sys.executable, str(ROOT / "scripts/setup_key.py"), "--init"], check=True)
    subprocess.run(["codex", "plugin", "marketplace", "add", str(MARKETPLACE_ROOT), "--json"], check=True)
    subprocess.run(["codex", "plugin", "add", "jev-codex-router@habib-local", "--json"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
