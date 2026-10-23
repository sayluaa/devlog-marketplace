#!/usr/bin/env python
"""find_outputs.py - 코드 파일이 만든 이미지/영상 결과물을 찾아서 JSON으로 알려 준다.

사용법
  python find_outputs.py 코드1.py 코드2.py ... --root 작업폴더 --date 2026-10-14 \
      --log-dir 작업폴더/devlog --assets 작업폴더/devlog/assets/261014

옵션
  --date     이 날짜(하루)에 만들어진 파일만 '그 코드의 결과'로 인정한다.
             (옛날 파일이나 나중에 덮어쓴 파일을 결과로 착각하지 않기 위해서)
  --assets   주면 이미지는 이 폴더로 복사하고, 영상은 썸네일(JPG)을 만든다.
             안 주면 찾기만 한다 (아무것도 쓰지 않는다).
  --log-dir  개발일지(.md)를 저장할 폴더. 결과의 markdown 경로는 이 폴더 기준이다.
  --shots    직접 캡처한 화면을 모아 두는 폴더 (기본: <log-dir>/shots).
             파일 이름이 코드 파일 접두사(v05_07 등)로 시작하면 그 코드의 결과로 붙는다.

confidence (일지에 얼마나 믿고 넣을지)
  high    코드에서 '저장'하는 줄로 확인된 파일 / runs 폴더에서 하나로 좁혀진 파일 / 직접 캡처
          -> markdown 이 만들어지고, --assets 가 있으면 복사/썸네일도 만든다
  medium  그날 만들어졌지만 결과인지 단정하기 어려운 파일(입력 파일일 수도 있다)
          -> 글에 넣지 않는다(markdown 이 null). 사용자가 확인하면 --include-medium 으로 다시 실행한다
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT

# 따옴표 안의 문자열 중 미디어 확장자로 끝나는 것 (예: "./bright_img.jpg")
LITERAL = re.compile(
    r"""(['"])([^'"\n]+?\.(?:jpe?g|png|gif|webp|bmp|mp4|avi|mov|mkv|webm))\1""", re.I)
ASSIGN = re.compile(r"^\s*(\w+)\s*=")  # output_path = "x.jpg"  ->  변수 이름 'output_path'
SAVE_TRUE = re.compile(r"save\s*=\s*True")  # YOLO: model(..., save=True) -> runs/ 에 저장됨
SCREEN_ONLY = re.compile(r"imshow|plt\.show|\.launch\(|st\.image|\.image\(")
WRITES_SOMETHING = re.compile(r"imwrite|savefig|VideoWriter|\.save\(|to_file")
# 모델 이름에 든 힌트 -> runs/ 아래 폴더 이름 (예: yolo11n-pose.pt -> runs/pose)
TASK_HINTS = {"-pose": "pose", "-seg": "segment", "-cls": "classify", "-obb": "obb"}


def classify_line(line):
    """코드 한 줄을 보고 이 줄이 '결과를 저장'하는지 '입력을 읽는지' 판단한다.

    반환값: "output" (결과 저장) | "input" (입력 읽기) | "unknown" (모르겠음)
    "unknown"이면 파일이 그날 만들어졌는지(수정 시각)만 보고 '추정'으로 취급한다.
    """
    if "imwrite" in line:
        return "output"
    if "imread" in line:
        return "input"
    # TODO(human): 위 두 가지 말고도 수업 코드에는 저장/읽기 패턴이 더 있다.
    #   예) image.save(...), plt.savefig(...), cv2.VideoWriter(...), cv2.VideoCapture(...),
    #       open(경로, "wb") ...
    #   (model(..., save=True)는 아래 find_in_runs()가 따로 처리하니 여기서는 신경 쓰지 않아도 된다)
    #   애매한 것(open은 읽기도 쓰기도 한다)은 "unknown"으로 두는 편이 안전할 수 있다.
    return "unknown"


def role_of_line(index, lines):
    """index번째 줄에 적힌 경로가 입력인지 출력인지 판단한다.

    경로를 변수에 담아 두고(output_path = "x.jpg") 다른 줄에서 쓰는(cv2.imwrite(output_path, ...))
    경우가 많아서, 그 줄에서 못 알아내면 같은 변수를 쓰는 다른 줄에서 힌트를 얻는다.
    """
    if SAVE_TRUE.search(lines[index]):  # model("영상.mp4", save=True): 적힌 경로는 입력이고 결과는 runs/ 에 생긴다
        return "input"
    role = classify_line(lines[index])
    if role != "unknown":
        return role
    m = ASSIGN.match(lines[index])
    if m:
        name = re.compile(r"\b%s\b" % re.escape(m.group(1)))
        for j, other in enumerate(lines):
            if j != index and name.search(other):
                role = classify_line(other)
                if role != "unknown":
                    return role
    return "unknown"


def made_that_day(path, window):
    start, end = window
    return start <= datetime.fromtimestamp(path.stat().st_mtime) < end


def resolve(rel_text, bases):
    """코드에 적힌 경로가 실제로 어디 있는지 찾는다. 스크립트를 실행한 위치를 모르니 여러 곳을 본다."""
    p = Path(rel_text)
    if p.is_absolute():
        return p if p.is_file() else None
    for base in bases:
        if (base / p).is_file():
            return (base / p).resolve()
    return None


def find_in_runs(stem, task, root, window):
    """YOLO가 save=True로 runs/ 아래에 저장한 결과를 입력 파일 이름(stem)으로 찾는다.

    같은 영상으로 pose/segment를 둘 다 돌렸다면 모델 이름 힌트(task)가 맞는 쪽을 먼저 고른다.
    돌려주는 값: (가장 알맞은 파일 또는 None, 후보 개수)
    """
    runs = root / "runs"
    if not runs.is_dir():
        return None, 0
    hits = [p for p in runs.rglob("*")
            if p.is_file() and p.stem == stem and p.suffix.lower() in MEDIA_EXT
            and made_that_day(p, window)]
    hits.sort(key=lambda p: (task not in p.parts, len(p.parts), -p.stat().st_mtime))
    candidates = [p for p in hits if task in p.parts] or hits  # 모델 힌트에 맞는 것이 있으면 그것만 센다
    return (hits[0], len(candidates)) if hits else (None, 0)


def find_shots(code_path, shots_dir):
    """직접 캡처해 둔 파일 찾기. v05_07_yolo_region.py -> v05_07.png, v05_07_결과.png ..."""
    if not shots_dir.is_dir():
        return []
    m = re.match(r"(v\d+_\d+)", code_path.stem)
    key = m.group(1) if m else code_path.stem
    found = list(shots_dir.glob(key + ".*")) + list(shots_dir.glob(key + "_*"))
    return sorted(p for p in found if p.suffix.lower() in MEDIA_EXT)


def rel(path, base):
    """base 기준 상대경로 (슬래시 / 로 통일, 공백은 %20)."""
    try:
        text = os.path.relpath(str(path), str(base)).replace("\\", "/")
    except ValueError:  # 드라이브가 다르면 상대경로를 만들 수 없다
        text = Path(path).as_uri()
    return text.replace(" ", "%20")


def safe_name(name):
    """파일 이름의 공백/특수문자를 _로 바꾼다 (한글은 그대로 둔다)."""
    return re.sub(r"[^\w.\-]", "_", name)


def make_thumbnail(video, dest):
    """영상 가운데 프레임을 JPG로 저장한다. 실패하면 이유(문자열)를, 성공하면 None을 돌려준다."""
    try:
        import cv2
    except ImportError:
        return "opencv(cv2)가 없어 썸네일을 만들지 못했다"
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return "영상에서 프레임을 읽지 못했다"
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return "썸네일 인코딩에 실패했다"
    buf.tofile(str(dest))  # 한글 경로에서도 저장되도록 cv2.imwrite 대신 numpy로 쓴다
    return None


def describe(path, source, confidence, line, code_path, ctx):
    """결과 파일 하나를 설명하는 dict를 만든다. ctx.assets가 있으면 복사/썸네일도 만든다."""
    kind = "image" if path.suffix.lower() in IMAGE_EXT else "video"
    item = {"kind": kind, "source": source, "confidence": confidence, "line": line,
            "original": rel(path, ctx.root), "size_mb": round(path.stat().st_size / 1024 / 1024, 2)}
    if confidence != "high" and not ctx.include_medium:
        # 입력 파일이 결과로 둔갑하면 공개 글이 거짓이 된다. 글에 넣지 않고 사용자 확인용 후보로만 알린다
        item["markdown"] = None
        return item
    name = path.name
    shown = path if kind == "image" else None  # 일지에 보일 이미지(원본/복사본). 영상은 썸네일을 만들었을 때만 생긴다
    if ctx.assets is not None:
        ctx.assets.mkdir(parents=True, exist_ok=True)
        prefix = safe_name(code_path.stem)
        if kind == "image":
            shown = ctx.assets / ("%s__%s" % (prefix, safe_name(name)))
            shutil.copy2(str(path), str(shown))
        else:
            shown = ctx.assets / ("%s__%s_thumb.jpg" % (prefix, safe_name(path.stem)))
            problem = make_thumbnail(path, shown)
            if problem:
                item["warning"] = problem
                shown = None
    if kind == "image":
        item["markdown"] = "![%s](%s)" % (name, rel(shown, ctx.log_dir))
    elif shown is not None:
        item["markdown"] = "[![영상: %s](%s)](%s)" % (
            name, rel(shown, ctx.log_dir), rel(path, ctx.log_dir))
    else:
        item["markdown"] = "[영상 보기: %s](%s)" % (name, rel(path, ctx.log_dir))
    return item


def analyze(code_path, ctx):
    text = code_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    bases = [code_path.parent, ctx.root, code_path.parent.parent]
    task = next((v for k, v in TASK_HINTS.items() if k in text), None)
    outputs, inputs, stems, seen = [], [], [], set()

    def keep(path, source, confidence, line=None):
        key = str(path.resolve())
        if key not in seen:  # 같은 파일을 두 번 넣지 않는다
            seen.add(key)
            outputs.append(describe(path, source, confidence, line, code_path, ctx))

    # 1. 코드에 적힌 이미지/영상 경로 -> 실제 파일이 있고 그날 만들어졌으면 결과 후보
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):  # 주석에 적힌 경로는 실제로 실행되는 코드가 아니다
            continue
        for m in LITERAL.finditer(line):
            rel_text = m.group(2)
            if "://" in rel_text or "{" in rel_text:  # URL, f-string은 건너뛴다
                continue
            stems.append(Path(rel_text).stem)
            found = resolve(rel_text, bases)
            if found is None:
                continue
            role = role_of_line(i, lines)
            if role == "input":
                inputs.append(rel(found, ctx.root))
            elif made_that_day(found, ctx.window):
                keep(found, "literal", "high" if role == "output" else "medium", i + 1)

    # 2. save=True 이면 결과는 runs/ 폴더에 입력 파일과 같은 이름으로 저장된다
    if SAVE_TRUE.search(text):
        for stem in dict.fromkeys(stems):
            hit, count = find_in_runs(stem, task, ctx.root, ctx.window)
            if hit:
                keep(hit, "runs", "high" if count == 1 else "medium")

    # 3. 사용자가 직접 캡처해 둔 화면
    for shot in find_shots(code_path, ctx.shots):
        keep(shot, "shots", "high")

    notes = []
    if not outputs:
        if SCREEN_ONLY.search(text):
            notes.append("결과가 화면에만 표시된다(imshow/show/launch 등). 일지에 넣으려면 화면을 캡처해 "
                         "%s 에 '%s.png' 처럼 저장한다." % (rel(ctx.shots, ctx.root), code_path.stem[:6]))
        elif WRITES_SOMETHING.search(text):
            notes.append("저장하는 코드는 있으나 저장 경로를 특정하지 못했다(경로가 계산되거나 그날 만든 파일이 아님).")
        else:
            notes.append("결과 파일을 만드는 코드가 없다.")
    return {"code": rel(code_path, ctx.root), "outputs": outputs, "inputs": inputs, "notes": notes}


def parse_date(text):
    return datetime.strptime(text, "%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser(description="코드가 만든 이미지/영상 결과물 찾기")
    ap.add_argument("code_files", nargs="+")
    ap.add_argument("--root", default=".")
    ap.add_argument("--date", type=parse_date, default=None, help="YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--assets", default=None)
    ap.add_argument("--shots", default=None)
    ap.add_argument("--include-medium", action="store_true",
                    help="확신이 낮은(medium) 후보도 복사/썸네일을 만들고 markdown을 만든다 (사용자가 확인한 뒤에만 쓴다)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    day = args.date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    log_dir = Path(args.log_dir).resolve() if args.log_dir else root / "devlog"
    ctx = SimpleNamespace(
        root=root, log_dir=log_dir, window=(day, day + timedelta(days=1)),
        include_medium=args.include_medium,
        assets=Path(args.assets).resolve() if args.assets else None,
        shots=Path(args.shots).resolve() if args.shots else log_dir / "shots")

    files = [analyze(Path(c).resolve(), ctx) for c in args.code_files]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔에서도 한글이 깨지지 않게
    print(json.dumps({"date": day.strftime("%Y-%m-%d"), "files": files},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
