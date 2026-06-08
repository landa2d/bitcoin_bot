#!/usr/bin/env python3
"""Dependency-free Markdown -> styled, self-contained HTML for operator review.

No external deps (the box has no `markdown`/`pandoc` and pip is PEP-668 locked).
Handles the constructs GSD planning docs use: ATX headings, pipe tables, fenced
code, inline code, bold, links, unordered/ordered lists, horizontal rules, and
paragraphs. Output is a single self-contained .html with embedded CSS.

Usage: python3 md_to_html.py <input.md> <output.html>
"""
import html
import re
import sys


def render_inline(text: str) -> str:
    """Escape HTML, then re-introduce inline markdown as safe tags.

    Inline code is protected first so its contents are never re-parsed.
    """
    placeholders: list[str] = []

    def stash(rendered: str) -> str:
        placeholders.append(rendered)
        return f"\x00{len(placeholders) - 1}\x00"

    # 1) inline code: capture raw, escape, stash
    def code_sub(m: re.Match) -> str:
        return stash(f"<code>{html.escape(m.group(1))}</code>")

    text = re.sub(r"`([^`]+)`", code_sub, text)

    # 2) escape the rest of the line
    text = html.escape(text)

    # 3) links [text](url)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        text,
    )
    # 4) bold then italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)([^*]+?)\*(?!\*)", r"<em>\1</em>", text)

    # 5) restore stashed code spans
    def unstash(m: re.Match) -> str:
        return placeholders[int(m.group(1))]

    return re.sub(r"\x00(\d+)\x00", unstash, text)


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def is_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:?-]*-[\s:|?-]*\|?\s*$", line)) and "-" in line


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # fenced code
        m = re.match(r"^```(\w*)\s*$", line)
        if m:
            lang = m.group(1)
            i += 1
            buf: list[str] = []
            while i < n and not re.match(r"^```\s*$", lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            cls = f' class="lang-{lang}"' if lang else ""
            out.append(
                f"<pre><code{cls}>" + html.escape("\n".join(buf)) + "</code></pre>"
            )
            continue

        # table: header line followed by separator
        if "|" in line and i + 1 < n and is_separator(lines[i + 1]):
            header = split_row(line)
            i += 2  # skip header + separator
            rows: list[list[str]] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(split_row(lines[i]))
                i += 1
            thead = "".join(f"<th>{render_inline(c)}</th>" for c in header)
            body = ""
            for r in rows:
                cells = "".join(f"<td>{render_inline(c)}</td>" for c in r)
                body += f"<tr>{cells}</tr>"
            out.append(
                f"<table><thead><tr>{thead}</tr></thead><tbody>{body}</tbody></table>"
            )
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{render_inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue

        # horizontal rule
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # unordered list
        if re.match(r"^\s*[-*+]\s+", line):
            items: list[str] = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]))
                i += 1
            out.append(
                "<ul>" + "".join(f"<li>{render_inline(it)}</li>" for it in items) + "</ul>"
            )
            continue

        # ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            out.append(
                "<ol>" + "".join(f"<li>{render_inline(it)}</li>" for it in items) + "</ol>"
            )
            continue

        # blank line
        if not line.strip():
            i += 1
            continue

        # paragraph (gather until blank / block start)
        para: list[str] = []
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,6}\s|```|\s*[-*+]\s|\s*\d+\.\s|\s*(-{3,}|\*{3,}|_{3,})\s*$)", lines[i]
        ):
            if "|" in lines[i] and i + 1 < n and is_separator(lines[i + 1]):
                break
            para.append(lines[i])
            i += 1
        out.append("<p>" + render_inline(" ".join(para)) + "</p>")

    return "\n".join(out)


CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { max-width: 900px; margin: 2rem auto; padding: 0 1.25rem 4rem;
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: #1a1f29; background: #fafbfc; }
h1, h2, h3, h4 { line-height: 1.25; margin-top: 2rem; color: #0f1623; }
h1 { font-size: 1.9rem; border-bottom: 2px solid #e3e8ee; padding-bottom: .4rem; }
h2 { font-size: 1.4rem; border-bottom: 1px solid #e8edf2; padding-bottom: .3rem; }
h3 { font-size: 1.15rem; } h4 { font-size: 1rem; }
p { margin: .8rem 0; }
a { color: #1c6fd6; }
code { font: 13.5px/1.5 "SF Mono", ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
  background: #eef1f5; padding: .12em .4em; border-radius: 4px; color: #11324d; }
pre { background: #0f1623; color: #e8edf2; padding: 1rem 1.1rem; border-radius: 8px;
  overflow-x: auto; font-size: 13.5px; line-height: 1.55; }
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1.1rem 0; font-size: 14.5px;
  box-shadow: 0 0 0 1px #e3e8ee; border-radius: 8px; overflow: hidden; }
th, td { border-bottom: 1px solid #e8edf2; padding: .55rem .7rem; text-align: left; vertical-align: top; }
th { background: #f1f4f8; font-weight: 600; }
tr:last-child td { border-bottom: none; }
tbody tr:nth-child(even) { background: #f7f9fb; }
ul, ol { padding-left: 1.4rem; } li { margin: .3rem 0; }
hr { border: none; border-top: 1px solid #e3e8ee; margin: 2rem 0; }
.review-banner { background: #fff8e6; border: 1px solid #f0d98a; color: #6b5208;
  padding: .6rem .9rem; border-radius: 8px; font-size: 13.5px; margin-bottom: 1.5rem; }
.review-banner strong { color: #6b5208; }
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: md_to_html.py <input.md> <output.html>", file=sys.stderr)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        md = f.read()
    title = re.sub(r"\.md$", "", src.rsplit("/", 1)[-1])
    body = convert(md)
    doc = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f'<div class="review-banner"><strong>Review copy</strong> — rendered from '
        f"<code>{html.escape(src)}</code>. The markdown source is authoritative.</div>\n"
        f"{body}\n</body>\n</html>\n"
    )
    with open(dst, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote {dst} ({len(doc)} bytes) from {src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
