# devlog — 오늘 배운 수업 코드를 블로그용 개발일지로

그날 수업 코드를 읽고, **핵심 요약 + 초보자용 주석을 단 중요 코드 + 코드가 만든 이미지·영상 결과물(코드 바로 아래)**을
한 편의 글로 만들어 줍니다. 결과는 마크다운(`.md`)과, 네이버 블로그 등에 붙여넣는 HTML(`.html`)로 저장됩니다.
원본 코드는 수정하지 않습니다.

## 설치 (Claude Code 안에서)

```
/plugin marketplace add sayluaa/devlog-marketplace
/plugin install devlog@sayluaa-marketplace
```

설치 후 Claude Code를 다시 시작하거나 `/reload-plugins`를 입력하세요.

## 사용

수업 폴더에서 Claude Code를 열고:

```
/devlog:devlog            ← 오늘 날짜
/devlog:devlog 261014     ← 날짜 지정
```

"오늘 개발일지 써줘"처럼 말해도 됩니다. 만들어지는 것은 작업 폴더의 `devlog/` 아래 `YYMMDD.md`, `YYMMDD.html`, `assets/`입니다.

## 필요한 것

- Claude Code
- Python 3 (스크립트 실행용)
- OpenCV(`cv2`)는 선택입니다. 없으면 영상은 썸네일 없이 링크로만 들어갑니다.

## 업데이트·삭제

```
claude plugin marketplace update sayluaa-marketplace
claude plugin marketplace remove sayluaa-marketplace
```

## 알아 둘 점

- 폴더 이름이 `YYMMDD_번호_주제` 형태일 때 그날 코드를 가장 잘 찾습니다.
- 결과가 화면에만 뜨는 코드(`imshow`, Gradio, Streamlit)는 이미지가 자동으로 붙지 않습니다.
  화면을 캡처해 `devlog/shots/`에 코드 파일 접두사(예: `v05_07.png`)로 저장하면 다음에 붙습니다.
- 네이버 블로그 붙여넣기는 제한적으로 확인했고, 다른 블로그는 아직 확인하지 못했습니다. `references/blog-guide.md`를 참고하세요.
