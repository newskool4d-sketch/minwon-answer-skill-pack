# 민원 답변 스킬팩

> 버전: 1.1 / 최종 수정: 2026-06-11 (원천 매뉴얼 분석 기준일: 2026-05-02)

민원, 고충민원, 제안, 예산낭비신고, 제도개선, 민원·정책 질의응답, 국민생각함, 선순환 이슈카드 관련 답변 초안 작성을 지원하는 범용 AI 작업 지침 패키지입니다.

이 패키지는 Codex, Claude Code, Gemini CLI에서 모두 사용할 수 있도록 벤더 중립 핵심 지침과 도구별 래퍼를 분리합니다.

## 사용 대상

- 교육청, 직속기관, 공공기관의 민원 답변 초안 작성
- 국민신문고·국민생각함·제안·예산낭비신고 처리 흐름 점검
- 법령 근거, 소관 여부, 이송·협조·다부처 판단이 필요한 민원 검토
- Markdown 초안 작성 후 HWPX 변환이 필요한 행정문서 작업

## 폴더 구조

```text
minwon-answer-skill-pack/
├── README.md
├── core/
│   ├── workflow.md
│   ├── response-rules.md
│   └── quality-checklist.md
├── references/
│   ├── source-manual-index.md
│   ├── complaint-types.md
│   ├── routing-and-jurisdiction.md
│   ├── deadlines-and-followup.md
│   ├── privacy-and-disclosure.md
│   ├── tools-and-output.md
│   └── local-context.md
├── codex/
│   └── SKILL.md
├── claude-code/
│   └── CLAUDE.md
├── gemini-cli/
│   └── GEMINI.md
├── tools/
│   └── convert-output.md
└── examples/
    ├── minwon-answer-template.md
    └── golden-cases.md
```

### 배포 구조 안내

이 저장소는 원본(source of truth)입니다. 각 도구의 스킬 폴더에 배포할 때는 구조가 달라집니다.

- Codex 배포(`~/.codex/skills/minwon-answer/`): `codex/SKILL.md`를 루트 `SKILL.md`로 이동하고 내부 상대경로의 `../`를 제거합니다. `claude-code/`, `gemini-cli/` 래퍼 폴더는 배포하지 않습니다.
- Claude Code 배포(`~/.claude/skills/minwon-answer/`): Codex 배포본과 같은 구조를 사용합니다 (루트 `SKILL.md`의 frontmatter를 그대로 활용).
- 따라서 배포본에서는 이 README의 폴더 구조도와 실제 구조가 다를 수 있습니다.

## 기본 실행 원칙

1. 민원 유형을 먼저 분류합니다.
2. 소관, 처리권한, 이송·협조·다부처 필요 여부를 판단합니다.
3. 사실관계, 법령근거, 개인정보, 처리기간을 확인합니다.
4. 결론, 근거, 조치사항, 향후 절차, 문의 안내 순서로 답변합니다.
5. 불확실한 내용은 추정하지 않고 `[확인 필요: 항목]`으로 표시합니다.
6. 기본 산출물은 `.md`로 작성하고, 필요 시 HWPX로 변환합니다.

## 도구 연계

- 법령검토: `korean-law-mcp`
- 최신 검색: `insane-search`
- 심층 조사: `deep-research`
- HWPX 변환: `to_hwpx_com.py` (`tools/convert-output.md` 참조)
- 도구가 없는 환경의 대체 절차: `references/tools-and-output.md`의 "도구 부재 시 대체 절차" 참조

## GitHub 업로드 전 점검

- 원본 HWPX 매뉴얼은 포함하지 않는 것을 권장합니다.
- 공개 저장소에 올릴 경우 기관 내부 정보, 개인정보, 비공개 화면 캡처, 계정 정보가 포함되지 않았는지 확인합니다.
- `references/source-manual-index.md`에는 원문 파일명과 분석 요지만 남기고 원문 전문은 넣지 않습니다.
