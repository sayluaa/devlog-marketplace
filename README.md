# devlog — 오늘 배운 수업 코드를 블로그용 개발일지로

그날 수업 코드를 읽고, **핵심 요약 + 초보자용 주석을 단 중요 코드 + 코드가 만든 이미지·영상 결과물(코드 바로 아래)**을
한 편의 글로 만들어 줍니다. 결과는 마크다운(`.md`)과, 네이버 블로그 등에 붙여넣는 HTML(`.html`)로 저장됩니다.
원본 코드는 수정하지 않습니다.

## 설치 (Claude Code 안에서, 명령을 **한 줄씩 따로** 입력)

두 줄을 한꺼번에 복사해 붙여넣으면 한 입력칸에 합쳐져서 오류가 납니다. 1번을 입력하고 Enter, 성공 메시지를 확인한 뒤 2번을 입력하세요.

**1단계: 마켓플레이스 추가**

```
/plugin marketplace add sayluaa/devlog-marketplace
```

`✔ Successfully added marketplace`가 보이면 성공입니다.

**2단계: 플러그인 설치**

```
/plugin install devlog@sayluaa-marketplace
```

설치 후 Claude Code를 다시 시작하거나 `/reload-plugins`를 입력하세요.

> `/plugin marketplace add`만 입력하면 "Enter marketplace source" 창이 열립니다. 그 칸에는 `sayluaa/devlog-marketplace`만 넣으세요.
> 터미널에서는 `claude plugin marketplace add sayluaa/devlog-marketplace`, `claude plugin install devlog@sayluaa-marketplace`를 각각 따로 실행해도 됩니다.

## 사용

수업 폴더에서 Claude Code를 열고:

```
/devlog:daily            ← 오늘 날짜
/devlog:daily 261014     ← 날짜 지정
```

"오늘 개발일지 써줘"처럼 말해도 됩니다. 결과는 작업 폴더의 `devlog/` 아래 `YYMMDD.md`, `YYMMDD.html`, `assets/`에 저장됩니다.
`.html`을 브라우저로 열고 **[본문 복사]** 버튼을 누른 뒤 블로그 글쓰기 화면에 붙여넣으세요.

## 필요한 것

- Claude Code (Node.js는 필요 없습니다)
- git (마켓플레이스를 GitHub에서 받을 때 사용)
- Python 3 (스크립트 실행용)
- OpenCV(`cv2`)는 선택입니다. 없으면 영상은 썸네일 없이 링크로만 들어갑니다.

## 업데이트 · 삭제

```
claude plugin marketplace update sayluaa-marketplace
claude plugin update devlog@sayluaa-marketplace
claude plugin uninstall devlog@sayluaa-marketplace
claude plugin marketplace remove sayluaa-marketplace
```

## 설치가 안 될 때

1. 명령어를 **한 줄씩 따로** 입력했는지 확인하세요. 두 줄을 한꺼번에 붙여넣으면 `is not a valid GitHub owner/repo shorthand` 오류가 납니다.
   저장소 주소가 `sayluaa/devlog-marketplace`가 맞는지도 확인하세요. 주소가 틀려도 `Could not read from remote repository` 오류가 납니다.
2. `claude --version`이 너무 오래된 버전이면 업데이트하세요.
3. 줄임 주소가 안 되면 전체 주소로 시도하세요: `/plugin marketplace add https://github.com/sayluaa/devlog-marketplace.git`
4. 그래도 안 되면 에러 메시지 전체를 알려 주세요.

## 알아 둘 점

- 폴더 이름이 `YYMMDD_번호_주제` 형태일 때 그날 코드를 가장 잘 찾습니다.
- 결과가 화면에만 뜨는 코드(`imshow`, Gradio, Streamlit)는 이미지가 자동으로 붙지 않습니다.
  화면을 캡처해 `devlog/shots/`에 코드 파일 접두사(예: `v05_07.png`)로 저장하면 다음에 붙습니다.
- 네이버 블로그 붙여넣기는 제한적으로 확인했고, 다른 블로그는 아직 확인하지 못했습니다. 스킬 폴더의 `references/blog-guide.md`를 참고하세요.
