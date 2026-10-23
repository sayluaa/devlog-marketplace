#!/usr/bin/env python
"""build_html.py - 개발일지 마크다운(.md)을 블로그에 붙여넣기 좋은 HTML로 바꾼다.

사용법
  python build_html.py devlog/261014.md          ->  devlog/261014.html 이 만들어진다
  브라우저로 .html 을 열고 [본문 복사] 버튼을 누른 뒤, 블로그 글쓰기 화면에서 Ctrl+V 한다.

왜 HTML인가
  네이버 블로그 같은 에디터는 마크다운을 받지 못하고, 내 컴퓨터에 있는 이미지 경로도
  불러오지 못한다. 그래서 이미지를 HTML 파일 안에 그대로 넣고(base64), 서식은 태그에
  직접 적어서(inline style) 복사-붙여넣기만으로 옮길 수 있게 만든다.

지원하는 마크다운 (일지 템플릿이 쓰는 것만)
  제목(# ## ###), 문단, 목록(- 한 단계), 인용(>), 구분선(---), 코드 블록(```),
  이미지, 웹 링크, `코드`, **굵게**, *기울임*
  표는 지원하지 않는다. 블로그 에디터에서 깨지기 쉬워서 목록으로 쓴다.

안전장치
  API 키처럼 보이는 문자열이 있으면 HTML을 만들지 않고 멈춘다(종료 코드 2).
  블로그는 공개되는 곳이라서다. 정말 괜찮다면 --force 로 무시할 수 있다.
"""
import argparse
import base64
import html
import mimetypes
import re
import sys
from pathlib import Path
from urllib.parse import unquote

SECRET_PATTERNS = [
    r"gsk_[A-Za-z0-9]{20,}",        # Groq
    r"sk-[A-Za-z0-9_-]{20,}",       # OpenAI, Anthropic 등
    r"AIza[0-9A-Za-z_-]{30,}",      # Google
    r"gh[pousr]_[A-Za-z0-9]{30,}",  # GitHub
    r"hf_[A-Za-z0-9]{20,}",         # Hugging Face
    r"(?i)(?:api[_-]?key|secret|token|password|client[_-]?id)\s*[=:]\s*['\"][^'\"\s]{8,}['\"]",
]
PLACEHOLDER = re.compile(r"YOUR|<[^>]+>|\*{3,}|x{4,}|\.{3}", re.I)  # YOUR_API_KEY 같은 자리표시자는 통과

HEADING = re.compile(r"^(#{1,3})\s+(.*)")
RULE = re.compile(r"^-{3,}\s*$")
BULLET = re.compile(r"^\s*[-*]\s+(.*)")
IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK_IMG = re.compile(r"\[(\x00IMG\d+\x00)\]\([^)\s]+\)")  # 사진에 걸린 링크: [![..](사진)](영상 경로)
LINK_WEB = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])\*(?![\s*])([^*\n]+?)\*(?![\w*])")

FONT_MONO = "Consolas,'D2Coding','Courier New',monospace"
HEADING_STYLE = {
    1: "font-size:1.7em;margin:0 0 14px",
    2: "font-size:1.35em;margin:30px 0 10px;padding-bottom:4px;border-bottom:1px solid #e5e8eb",
    3: "font-size:1.12em;margin:24px 0 8px",
}
PRE_STYLE = ("background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:12px 14px;"
             "font-family:%s;font-size:13px;line-height:1.55;word-break:break-word" % FONT_MONO)
# 에디터가 배경 서식을 지워도 구분되도록 굵게 + 색을 함께 쓴다 (네이버 붙여넣기 시험 결과 반영)
CODE_STYLE = ("background:#eff1f3;color:#c7254e;border-radius:4px;padding:1px 5px;"
              "font-family:%s;font-size:0.92em" % FONT_MONO)
QUOTE_STYLE = "margin:12px 0;padding:8px 14px;border-left:4px solid #b6c2cf;background:#f7f9fb;color:#444"

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
</head>
<body style="font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;max-width:760px;margin:24px auto;padding:0 16px;line-height:1.75;color:#222">
<div style="background:#eef6ff;border:1px solid #b6d4fe;padding:12px 16px;border-radius:8px;margin-bottom:28px;font-size:14px">
  <button id="copy" style="padding:6px 14px;font-size:14px;cursor:pointer">본문 복사</button>
  를 누른 뒤 블로그 글쓰기 화면에서 <b>Ctrl+V</b> 로 붙여넣으세요. (이 안내 상자는 복사되지 않습니다)
  <div id="msg" style="margin-top:6px;color:#0a58ca"></div>
</div>
<div id="post">
__BODY__
</div>
<script>
document.getElementById('copy').onclick = function () {
  var sel = window.getSelection();
  var range = document.createRange();
  range.selectNodeContents(document.getElementById('post'));
  sel.removeAllRanges();
  sel.addRange(range);
  var ok = false;
  try { ok = document.execCommand('copy'); } catch (e) {}
  document.getElementById('msg').textContent = ok
    ? '복사됐습니다. 블로그 글쓰기 화면에서 Ctrl+V 하세요.'
    : '자동 복사에 실패했습니다. 본문을 직접 드래그해서 Ctrl+C 하세요.';
};
</script>
</body>
</html>
"""


def find_secrets(md_text):
    """키처럼 보이는 문자열이 있는 줄 번호를 모은다. 키 전체를 화면에 다시 찍지 않도록 앞부분만 보여 준다."""
    hits = []
    for number, line in enumerate(md_text.splitlines(), 1):
        for pattern in SECRET_PATTERNS:
            m = re.search(pattern, line)
            if m and not PLACEHOLDER.search(m.group(0)):
                hits.append((number, m.group(0)[:10] + "..."))
    return hits


class Converter(object):
    def __init__(self, md_dir):
        self.md_dir = md_dir
        self.images = []   # 완성된 <img> 태그. 긴 base64를 정규식이 훑지 않도록 자리표시자로 다룬다
        self.embedded = 0
        self.problems = []

    def image(self, alt, src):
        alt, src = html.unescape(alt), unquote(html.unescape(src))
        if src.startswith(("http://", "https://", "data:")):
            url = src
        else:
            path = self.md_dir / src
            if not path.is_file():
                self.problems.append("이미지를 찾지 못했다: " + src)
                return html.escape("[이미지 없음: %s]" % src)
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            url = "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode("ascii"))
            self.embedded += 1
        self.images.append('<img src="%s" alt="%s" style="max-width:100%%;height:auto;display:block;margin:10px 0">'
                           % (url, html.escape(alt, quote=True)))
        return "\x00IMG%d\x00" % (len(self.images) - 1)

    def inline(self, text):
        # `코드` 조각은 자리표시자로 빼 두었다가 마지막에 되돌린다. 그래야 굵게/기울임 안에 코드가
        # 들어 있어도(**`save=True`** 처럼) 서식이 끊기지 않고, 코드 안의 * 는 서식으로 오해받지 않는다.
        codes = []

        def stash(m):
            codes.append('<span style="%s"><b>%s</b></span>' % (CODE_STYLE, html.escape(m.group(1))))
            return "\x01CODE%d\x01" % (len(codes) - 1)

        s = re.sub(r"`([^`\n]+)`", stash, text)
        s = html.escape(s, quote=False)
        s = IMG.sub(lambda m: self.image(m.group(1), m.group(2)), s)
        s = LINK_IMG.sub(r"\1", s)  # 로컬 영상 링크는 붙여넣어도 쓸모없어서 썸네일 사진만 남긴다
        s = LINK_WEB.sub(lambda m: '<a href="%s">%s</a>'
                         % (html.escape(html.unescape(m.group(2)), quote=True), m.group(1)), s)
        s = BOLD.sub(r"<b>\1</b>", s)
        s = ITALIC.sub(r"<i>\1</i>", s)
        return re.sub(r"\x01CODE(\d+)\x01", lambda m: codes[int(m.group(1))], s)

    @staticmethod
    def code_rows(code_lines):
        """코드를 한 줄에 div 하나씩으로 만든다. <pre>는 붙여넣을 때 줄바꿈이 사라지는 에디터가 있어서
        (네이버 시험 결과), 줄 단위 블록과 &nbsp; 들여쓰기로 줄바꿈과 들여쓰기를 고정한다."""
        rows = []
        for line in code_lines:
            line = line.expandtabs(4)
            rest = line.lstrip(" ")
            text = "&nbsp;" * (len(line) - len(rest)) + html.escape(rest).replace("  ", "&nbsp; ")
            rows.append('<div style="margin:0;min-height:1.55em">%s</div>' % (text or "&nbsp;"))
        return "".join(rows)

    @staticmethod
    def starts_block(line):
        return (line.startswith("```") or line.startswith("> ") or bool(HEADING.match(line))
                or bool(RULE.match(line)) or bool(BULLET.match(line)))

    def convert(self, md_text):
        lines = md_text.splitlines()
        out, i = [], 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
            elif line.startswith("```"):  # 코드 블록: 닫는 ``` 까지
                code = []
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    code.append(lines[i])
                    i += 1
                i += 1
                out.append('<div style="%s">%s</div>' % (PRE_STYLE, self.code_rows(code)))
            elif HEADING.match(line):
                hashes, title = HEADING.match(line).groups()
                out.append('<h%d style="%s">%s</h%d>' % (len(hashes), HEADING_STYLE[len(hashes)],
                                                         self.inline(title), len(hashes)))
                i += 1
            elif RULE.match(line):
                out.append('<hr style="border:none;border-top:1px solid #ddd;margin:26px 0">')
                i += 1
            elif line.startswith("> "):
                quote = []
                while i < len(lines) and lines[i].startswith(">"):
                    quote.append(lines[i][1:].strip())
                    i += 1
                out.append('<blockquote style="%s">%s</blockquote>'
                           % (QUOTE_STYLE, "<br>".join(self.inline(q) for q in quote)))
            elif BULLET.match(line):
                items = []
                while i < len(lines) and lines[i].strip():
                    m = BULLET.match(lines[i])
                    if m:
                        items.append(m.group(1))
                    elif lines[i][:1].isspace() and items:  # 들여쓴 줄은 앞 항목의 이어지는 내용
                        items[-1] += " " + lines[i].strip()
                    else:
                        break
                    i += 1
                out.append('<ul style="margin:8px 0;padding-left:22px">%s</ul>' % "".join(
                    '<li style="margin:4px 0">%s</li>' % self.inline(item) for item in items))
            else:
                para = []
                while i < len(lines) and lines[i].strip() and not (para and self.starts_block(lines[i])):
                    para.append(lines[i])
                    i += 1
                out.append('<p style="margin:10px 0">%s</p>' % "<br>".join(self.inline(p) for p in para))
        body = "\n".join(out)
        return re.sub(r"\x00IMG(\d+)\x00", lambda m: self.images[int(m.group(1))], body)


def main():
    ap = argparse.ArgumentParser(description="개발일지 .md 를 블로그 붙여넣기용 .html 로 변환")
    ap.add_argument("markdown")
    ap.add_argument("--force", action="store_true", help="키처럼 보이는 문자열이 있어도 만든다")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    md_path = Path(args.markdown).resolve()
    text = md_path.read_text(encoding="utf-8")

    secrets = find_secrets(text)
    if secrets and not args.force:
        print("중단: API 키처럼 보이는 문자열이 있어 HTML을 만들지 않았다. 자리표시자(YOUR_API_KEY)로 바꾼 뒤 다시 실행하세요.")
        for number, preview in secrets:
            print("  %d번째 줄: %s" % (number, preview))
        sys.exit(2)

    converter = Converter(md_path.parent)
    body = converter.convert(text)
    heading = re.search(r"^#\s+(.*)", text, re.M)
    title = html.escape(heading.group(1).replace("`", "")) if heading else "개발일지"
    page = PAGE.replace("__TITLE__", title).replace("__BODY__", body)

    out_path = md_path.with_suffix(".html")
    out_path.write_text(page, encoding="utf-8")
    print("만든 파일: %s (%.1f MB, 이미지 %d장 포함)" % (out_path, out_path.stat().st_size / 1024 / 1024,
                                                    converter.embedded))
    for problem in converter.problems:
        print("주의: " + problem)


if __name__ == "__main__":
    main()
