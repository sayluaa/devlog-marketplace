#!/usr/bin/env python
"""check_same_code.py - 주석을 단 코드가 원본과 '코드로서' 똑같은지 확인한다.

사용법
  python check_same_code.py 원본조각.py 주석단조각.py

코드를 낱말(토큰) 단위로 잘라서 비교한다. 주석, 빈 줄, 줄바꿈 위치는 무시하고
변수 이름, 숫자, 문자열, 연산자가 하나라도 다르면 알려 준다.
같으면 종료 코드 0, 다르면 1, 파이썬 조각으로 읽을 수 없으면 3.

왜 필요한가
  초보자용 주석을 달다 보면 모델이 눈에 띄는 오타를 '살짝' 고치고 싶어질 수 있다.
  일지의 코드는 학습자가 실제로 쓴 코드여야 하므로, 주석 외에 바뀐 게 없다는 걸 확인한다.
"""
import io
import sys
import textwrap
import tokenize
from pathlib import Path

# 비교에서 빼는 것: 주석, 줄바꿈, 들여쓰기 표시
IGNORED = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
           tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}


def code_tokens(path):
    text = textwrap.dedent(Path(path).read_text(encoding="utf-8"))  # 함수 안쪽에서 잘라 온 조각도 읽히게
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    return [t.string for t in tokens if t.type not in IGNORED]


def main():
    if len(sys.argv) != 3:
        print("사용법: python check_same_code.py 원본조각.py 주석단조각.py")
        sys.exit(64)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        original, annotated = code_tokens(sys.argv[1]), code_tokens(sys.argv[2])
    except (tokenize.TokenError, IndentationError, SyntaxError) as error:
        reason = error.args[0] if error.args else error
        print("읽을 수 없음: 조각이 중간에서 잘렸을 수 있다 (%s). 함수나 단계 단위로 완결되게 다시 자르세요." % reason)
        sys.exit(3)

    if original == annotated:
        print("OK: 주석과 공백 외에는 원본과 같다 (낱말 %d개)" % len(original))
        return
    for position, (a, b) in enumerate(zip(original, annotated)):
        if a != b:
            print("다름: %d번째 낱말에서 원본 %r -> 주석본 %r" % (position + 1, a, b))
            print("  원본 앞뒤:", " ".join(original[max(0, position - 4):position + 5]))
            print("  주석본 앞뒤:", " ".join(annotated[max(0, position - 4):position + 5]))
            break
    else:
        print("다름: 낱말 개수가 다르다 (원본 %d개, 주석본 %d개). 한쪽이 더 길다." % (len(original), len(annotated)))
    sys.exit(1)


if __name__ == "__main__":
    main()
