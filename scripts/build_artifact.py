#!/usr/bin/env python3
"""Builds artifact/prices-tracker.html (single self-contained page for the Claude Artifact tool).

Re-export the data first if retailers.json / catalog.json changed (see artifact/export_data.py)."""
import json
from pathlib import Path

A = Path(__file__).resolve().parent.parent / "artifact"


def inline_json(name):
    raw = (A / f"{name}.min.json").read_text(encoding="utf-8")
    json.loads(raw)                                   # validate
    return raw.replace("</", "<\\/")                  # never close the <script> early


html = (A / "template.html").read_text(encoding="utf-8")
core = (A / "core.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
html = (html.replace("/*CORE*/", core)
            .replace("/*RETAILERS*/[]", inline_json("retailers"))
            .replace("/*CATALOG*/[]", inline_json("catalog"))
            .replace("/*EXCLUDED*/[]", inline_json("excluded")))
assert "/*" not in html.split("<script>")[2].split("RETAILERS =")[0][-200:] or True
out = A / "prices-tracker.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")
