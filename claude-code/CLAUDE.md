# 민원 답변 스킬팩: Claude Code 지침

이 프로젝트에서 민원 답변 작업을 수행할 때는 다음 파일을 순서대로 읽고 적용한다.

1. `core/workflow.md`
2. `core/response-rules.md`
3. `core/quality-checklist.md`
4. 필요한 경우 `references/`의 관련 파일
5. 초안 작성 전 `examples/golden-cases.md`로 문체·구조 기준 확인
6. 기관 특화 정보가 필요한 경우에만 `references/local-context.md` 로드

## 작업 원칙

- 한국어로 답변한다.
- 먼저 민원 유형을 분류한다.
- 소관, 이송, 다부처, 협조, 보완요청, 처리기간, 개인정보, 법령근거를 확인한다.
- 근거 없는 사실은 단정하지 않고 `[확인 필요: 항목]`으로 표시한다.
- 기본 산출물은 Markdown으로 작성한다.
- HWPX가 필요하면 `tools/convert-output.md`에 따라 변환한다.

## Claude Code 사용 팁

- 원문 매뉴얼 전체를 한 번에 읽지 않는다.
- `references/source-manual-index.md`로 관련 업무 유형을 찾은 뒤 필요한 참조 파일만 읽는다.
- 파일 생성 시 GitHub 업로드를 고려하여 경로와 파일명을 ASCII 또는 명확한 한글로 유지한다.
- 공개 저장소에 올릴 때 원본 HWPX와 개인정보가 포함되지 않도록 확인한다.
