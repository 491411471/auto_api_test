import markdown
import sys
import pathlib

def md_to_html(md_path: str):
    # 读取你的 Markdown 测试报告
    md_text = pathlib.Path(md_path).read_text(encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>测试报告</title>

<!-- GitHub 风格 CSS（和 PyCharm 很像） -->
<style>
@import url('https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css');

body {{
    max-width: 960px;
    margin: 40px auto;
    padding: 0 24px;
    background: #ffffff;
}}

.markdown-body {{
    font-size: 14px;
    line-height: 1.6;
}}

table {{
    border-collapse: collapse;
    width: 100%;
}}

th, td {{
    border: 1px solid #d0d7de;
    padding: 6px 12px;
}}

pre {{
    background: #f6f8fa;
    padding: 12px;
    border-radius: 6px;
    overflow: auto;
}}
</style>
</head>

<body>
<article class="markdown-body">
{markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])}
</article>
</body>
</html>
"""

    out_path = md_path.replace(".md", ".html")
    pathlib.Path(out_path).write_text(html, encoding="utf-8")
    print(" HTML 报告已生成：", out_path)

if __name__ == "__main__":
    md_to_html(sys.argv[1])