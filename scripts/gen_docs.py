"""Regenerate COVERAGE.md and the profile block inside README.md from the code. Run: python scripts/gen_docs.py"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import coverage  # noqa: E402
from app.profiles import PROFILES, system_prompt  # noqa: E402

START, END = "<!-- PROFILES:START -->", "<!-- PROFILES:END -->"


def profiles_block() -> str:
    out = [START, ""]
    for p in PROFILES.values():
        out += [f"### `{p.key}` - {p.label}", "",
                f"- **Company (fictional):** {p.company}",
                f"- **Suggested target description:** {p.target_description}",
                f"- **Suggested competitor list:** {', '.join(p.competitors)}",
                "- **Suggested system instructions** (matches what the target discloses; the configuration ID is a per-dataset canary):", "",
                "```text", system_prompt(p, "<per-dataset configuration ID>"), "```", ""]
    out.append(END)
    return "\n".join(out)


def main() -> None:
    (ROOT / "COVERAGE.md").write_text(coverage.render_markdown().rstrip() + "\n")
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text()
        if START in text and END in text:
            head, rest = text.split(START, 1)
            _, tail = rest.split(END, 1)
            readme.write_text(head + profiles_block() + tail)
    print("docs regenerated")


if __name__ == "__main__":
    main()
