"""Generate an original, redistributable demonstration deck and speaker notes."""

import json
from pathlib import Path
import sys
from reportlab.pdfgen.canvas import Canvas


def create(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(path), pagesize=(960, 540))
    slides = [
        ("A clearer view", "Your ideas on screen. Your notes beside them.", "#1f3453"),
        ("One shared story", "Current slide, next step, and a little room to think.", "#16443e"),
        ("Keep the audience focused", "The audience sees only what you choose to present.", "#49374f"),
    ]
    for number, (title, subtitle, color) in enumerate(slides):
        pdf.setFillColor(color)
        pdf.rect(0, 0, 960, 540, fill=1, stroke=0)
        pdf.setFillColor("#f3efe7")
        pdf.setFont("Helvetica", 42)
        pdf.drawString(64, 400, title)
        pdf.setFont("Helvetica", 23)
        pdf.drawString(64, 335, subtitle)
        pdf.setStrokeColor("#93b5c6")
        pdf.setLineWidth(3)
        for radius in (40, 70, 100):
            pdf.circle(780, 160, radius, fill=0, stroke=1)
        pdf.setFont("Helvetica", 14)
        pdf.drawString(64, 48, f"PAGECUE     /     {number + 1:02}")
        pdf.showPage()
    pdf.save()
    path.with_suffix(".pdfpc").write_text(json.dumps({"pdfpcFormat": 2, "pages": [
        {"idx": 0, "note": "Start with the idea, then give the audience a moment to look.\n\n"
                            "中文讲稿：让观众专注于内容。讲者备注只显示在自己的屏幕上。\n\n"
                            "Use the arrow keys to advance. Press ? to hide keyboard help."},
        {"idx": 1, "note": "This is the second page. The timer and notes remain on the presenter screen."}
    ]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(create(sys.argv[1] if len(sys.argv) > 1 else "qa/demo.pdf"))
