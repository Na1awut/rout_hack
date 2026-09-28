"""Build phase13_report/site/live.html from live_template.html + sim_data.json.

site/live.html   standalone document, data embedded, links to index.html
--artifact DIR   also writes DIR/pourready-live.html (Claude Artifact fragment:
                 no doctype/head, loads sim_data.json next to it, absolute links)
"""
import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "site"
REPORT_ARTIFACT = "https://claude.ai/artifact/EAkmf4z3E4FtLtKFGzvkuT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", type=Path)
    args = ap.parse_args()

    tpl = (HERE / "live_template.html").read_text(encoding="utf-8")
    data = (HERE / "sim_data.json").read_text(encoding="utf-8")
    title = re.match(r"\s*<title>(.*?)</title>", tpl).group(1)
    body = re.sub(r"^\s*<title>.*?</title>\s*", "", tpl, count=1, flags=re.S)

    site_body = body.replace("__REPORT_LINK__", "index.html").replace(" __REPORT_ATTRS__", "")
    site_body = site_body.replace("<script>\n(function(){",
                                  '<script type="application/json" id="sim-data">' + data + "</script>\n<script>\n(function(){", 1)
    doc = ("<!doctype html>\n<html lang=\"th\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
           f"<title>{title}</title>\n</head>\n<body>\n{site_body}\n</body>\n</html>\n")
    (SITE / "live.html").write_text(doc, encoding="utf-8")
    print("wrote", SITE / "live.html", round(len(doc) / 1024), "KB")

    if args.artifact:
        frag = f"<title>{title}</title>\n" + body.replace("__REPORT_LINK__", REPORT_ARTIFACT).replace(
            "__REPORT_ATTRS__", 'target="_blank" rel="noopener"')
        args.artifact.mkdir(parents=True, exist_ok=True)
        (args.artifact / "pourready-live.html").write_text(frag, encoding="utf-8")
        (args.artifact / "sim_data.json").write_text(data, encoding="utf-8")
        print("wrote artifact fragment to", args.artifact)


if __name__ == "__main__":
    main()
