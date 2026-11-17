"""Render the study protocol as a printable standalone HTML document."""

import re
import html
from pathlib import Path


root = Path(__file__).resolve().parents[1]
document = (root / "study/Ari_Study_Protocol.md").read_text()
existing = (root / "public/protocol.html").read_text()
style = re.search(r"<style>(.*?)</style>", existing, re.DOTALL).group(1)


def inline(text: str) -> str:
    """Escape text and render the document's ordinary web links."""
    return re.sub(r"\[([^\]]+)\]\((https?://[^\s]+)\)", r'<a href="\2">\1</a>', html.escape(text))


blocks = []
lines = document.splitlines()
index = 0
while index < len(lines):
    line = lines[index]
    if not line.strip():
        index += 1
        continue
    if line.startswith("#"):
        level = len(line) - len(line.lstrip("#"))
        blocks.append(f"<h{level}>" + inline(line[level:].strip()) + f"</h{level}>")
        index += 1
    elif line.startswith("|"):
        rows = []
        while index < len(lines) and lines[index].startswith("|"):
            cells = [cell.strip() for cell in lines[index].strip("|").split("|")]
            if not all(re.fullmatch("[-: ]+", cell) for cell in cells):
                rows.append(cells)
            index += 1
        blocks.append(
            '<div class="table-wrap"><table><thead><tr>'
            + "".join("<th>" + inline(cell) + "</th>" for cell in rows[0])
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join("<td>" + inline(cell) + "</td>" for cell in row) + "</tr>" for row in rows[1:])
            + "</tbody></table></div>"
        )
    elif line.startswith("- ") or re.match(r"^\d+\. ", line):
        tag = "ul" if line.startswith("- ") else "ol"
        items = []
        while index < len(lines) and (lines[index].startswith("- ") or re.match(r"^\d+\. ", lines[index])):
            items.append(re.sub(r"^(?:- |\d+\. )", "", lines[index]))
            index += 1
        blocks.append("<" + tag + ">" + "".join("<li>" + inline(item) + "</li>" for item in items) + "</" + tag + ">")
    else:
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(r"^(#|\||- |\d+\. )", lines[index]):
            paragraph.append(lines[index])
            index += 1
        blocks.append("<p>" + inline(" ".join(paragraph)) + "</p>")

page = (
    '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ari study protocol v0.2</title><style>'
    + style
    + '</style><main><nav><a href="./index.html">← Ari</a><a href="./task-cards.html">Task cards</a><button class="print" onclick="window.print()">Print / save PDF</button></nav>'
    + "".join(blocks)
    + "</main></html>"
)
(root / "public/protocol.html").write_text(page)
