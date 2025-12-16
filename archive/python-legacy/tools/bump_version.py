import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_FILE = ROOT / "app" / "main.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"


def bump_app_version(version: str):
    txt = MAIN_FILE.read_text(encoding="utf-8")
    new_txt, count = re.subn(r'APP_VERSION\s*=\s*"(.*?)"', f'APP_VERSION = "{version}"', txt, count=1)
    if count != 1:
        raise RuntimeError("Non sono riuscito ad aggiornare APP_VERSION in app/main.py")
    MAIN_FILE.write_text(new_txt, encoding="utf-8")


def prepend_changelog(version: str, title: str | None):
    changelog = CHANGELOG_FILE.read_text(encoding="utf-8")
    section_header = f"## {version}"
    if section_header in changelog:
        return
    body = title or "Note versione da compilare."
    insertion = f"{section_header}\n- {body}\n\n"
    if changelog.startswith("#"):
        lines = changelog.splitlines()
        lines.insert(2, insertion.strip())
        CHANGELOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        CHANGELOG_FILE.write_text(insertion + changelog, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Aggiorna APP_VERSION e crea sezione in CHANGELOG.md.")
    parser.add_argument("version", help="Nuova versione, es. 4.2.1")
    parser.add_argument("--title", help="Titolo/nota per il changelog", default=None)
    args = parser.parse_args()
    bump_app_version(args.version)
    prepend_changelog(args.version, args.title)
    print(f"Versione aggiornata a {args.version}")


if __name__ == "__main__":
    main()
