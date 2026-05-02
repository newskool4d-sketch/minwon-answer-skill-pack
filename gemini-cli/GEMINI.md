# 민원 답변 스킬팩: Gemini CLI 지침

Gemini CLI에서 이 스킬팩을 사용할 때는 저장소 루트에서 다음 지침을 따른다.

## 참조 순서

```text
core/workflow.md
core/response-rules.md
core/quality-checklist.md
references/source-manual-index.md
```

필요한 경우 다음 파일을 추가로 읽는다.

- `references/complaint-types.md`
- `references/routing-and-jurisdiction.md`
- `references/deadlines-and-followup.md`
- `references/privacy-and-disclosure.md`
- `references/tools-and-output.md`

## 기본 프롬프트

```text
이 저장소의 민원 답변 스킬팩 지침을 적용해 민원 유형을 분류하고, 소관·처리기간·법령근거·개인정보를 점검한 뒤 Markdown 형식의 답변 초안을 작성해 주세요. 확인되지 않은 사실은 [확인 필요: 항목]으로 표시해 주세요.
```

## 출력 규칙

- 내부 검토용과 대민 발송용을 구분한다.
- 대민 발송용에는 `[확인 필요]`, 내부 판단표, 도구 사용 로그를 남기지 않는다.
- 법령이나 최신 자료가 필요한 경우 도구 사용 가능 여부를 먼저 확인한다.
