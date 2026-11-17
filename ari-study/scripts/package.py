"""Package the study source, printable protocol and a self-contained demo."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


root = Path(__file__).resolve().parents[1]
output = root.parent / "deliverables/Ari_Phone_Robot_Study_v2.zip"
output.parent.mkdir(exist_ok=True)

preview = (root / "public/index.html").read_text()
preview = preview.replace(
    '<link rel="stylesheet" href="./style.css">',
    "<style>" + (root / "public/style.css").read_text() + "</style>",
)
preview = preview.replace(
    '<script defer src="./bundle.js"></script>',
    "<script>" + (root / "public/bundle.js").read_text().replace("</script", "<\\/script") + "</script>",
)
preview = preview.replace('<option value="live">Live voice</option>', "")
preview = preview.replace(
    '<button class="button secondary" id="health-check">',
    '<button class="button secondary" id="health-check" disabled>',
)
preview = preview.replace(
    "Check the server before a live session.", "Standalone scripted preview. Use the server app for live voice."
)
preview = preview.replace("Your microphone starts when you begin.", "Scripted preview: no microphone or live model.")
preview = preview.replace("./index.html", "./Ari_Phone_Preview.html")
preview = preview.replace("./protocol.html", "./Ari_Study_Protocol.html")
protocol = (root / "public/protocol.html").read_text()
protocol = protocol.replace("./index.html", "./Ari_Phone_Preview.html")
protocol = protocol.replace("./task-cards.html", "./public/task-cards.html")

excluded = {".git", ".netlify", "__pycache__", "recordings"}
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if excluded.intersection(relative.parts) or path.suffix == ".pyc":
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if relative.parts[0] == "node_modules" and relative.parts[1] != "ws":
            continue
        archive.write(path, "ari-study/" + relative.as_posix())
    guide = root.parent / "README.md"
    if guide.exists():
        archive.writestr("ari-study/README.md", guide.read_text())
    archive.writestr("ari-study/Ari_Phone_Preview.html", preview)
    archive.writestr("ari-study/Ari_Study_Protocol.html", protocol)

with ZipFile(output) as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    assert "ari-study/node_modules/ws/LICENSE" in names
    assert "ari-study/robot/voice_client.py" in names
    assert "ari-study/.env" not in names
    assert "With background researcher" in archive.read("ari-study/Ari_Phone_Preview.html").decode()
    assert "research_followup_skipped" in archive.read("ari-study/server/session.mjs").decode()
print(f"Created {output} ({len(names)} files, {output.stat().st_size:,} bytes)")
