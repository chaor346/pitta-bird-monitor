# -*- coding: utf-8 -*-
"""design_report.md -> design_report.pdf (via markdown -> HTML -> Edge headless)"""
import markdown, pathlib, subprocess, sys, os

root = pathlib.Path(r"D:\嵌赛\pitta_bird_monitor\report")
md_path = root / "design_report.md"
html_path = root / "_design_report.html"
pdf_path = root / "design_report.pdf"

md_text = md_path.read_text(encoding="utf-8")
body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>仙八色鸫监测系统设计报告</title>
<style>
@page {{ size: A4; margin: 18mm 16mm; }}
body {{ font-family: "Microsoft YaHei","SimSun",sans-serif; font-size: 10.5pt; line-height: 1.55; color:#222; }}
h1 {{ font-size: 18pt; border-bottom: 2px solid #333; padding-bottom: 6px; }}
h2 {{ font-size: 14pt; margin-top: 18px; border-bottom: 1px solid #999; padding-bottom: 3px; }}
h3 {{ font-size: 12pt; margin-top: 12px; color:#333; }}
table {{ border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 8px 0; }}
th, td {{ border: 1px solid #888; padding: 4px 6px; text-align: left; vertical-align: top; }}
th {{ background: #f0f0f0; }}
code {{ background:#f4f4f4; padding:1px 4px; border-radius:3px; font-family: Consolas,monospace; font-size:9.5pt; }}
pre {{ background:#f6f8fa; padding:8px; border-radius:4px; font-size:9pt; overflow-x:auto; }}
pre code {{ background:transparent; padding:0; }}
blockquote {{ border-left:3px solid #bbb; margin:6px 0; padding:4px 10px; color:#555; background:#fafafa; }}
</style></head><body>
{body}
</body></html>"""

html_path.write_text(html, encoding="utf-8")
print(f"HTML: {html_path} ({len(html)} bytes)")

edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
cmd = [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
       f"--print-to-pdf={pdf_path}", html_path.as_uri()]
print("Running:", " ".join(cmd))
r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
print("rc:", r.returncode)
if r.stderr: print("stderr:", r.stderr[:500])
if pdf_path.exists():
    print(f"PDF: {pdf_path} ({pdf_path.stat().st_size//1024} KB)")
else:
    print("PDF NOT generated")
    sys.exit(1)
