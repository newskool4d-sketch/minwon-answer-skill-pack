# 민원 답변 스킬팩

> 버전: 1.4.2 / 최종 수정: 2026-10-25 (원천 매뉴얼 분석 기준일: 2026-05-02)
> v1.4.2: `scripts/sanitize.py`의 이모지 결합·이형 선택자 판정을 근사 범위에서 Unicode 17.0 공식 표(emoji-zwj-sequences·emoji-variation-sequences·StandardizedVariants)로 교체 — ZWJ 묶음은 공식 시퀀스와 정확히 일치할 때만, VS1~3은 통합 한자의 공식 쌍일 때만 보존하고 한자 외 표준 이형 표기는 경고와 함께 제거, Python 유니코드 데이터 버전과 무관하게 Emoji 17 시퀀스 인식. 배포 저장소 안내·`tools/convert-output.md` 경로 표기 정리
> v1.4.1: 처리기간 연장 요약을 현행 시행령 제21조로 갱신(제4항 준용 문언은 해석 사항으로 표시), 행정심판 청구절차·관할 위원회 근거(행정심판법 제6·23조, `references/local-context.md`), 국민제안 요건 비해당 건의 보완·종결 처리와 불채택 재심사·반복 제안 기준(「국민 제안 규정」 제6·10·12조, `references/complaint-types.md`), `scripts/sanitize.py` 단독 CR 줄바꿈 처리·정상 이모지 시퀀스(이모지 사이 ZWJ, RGI 하위 지역 깃발 3종) 보존과 보존 건수 보고, 이형 선택자 기반 제한(VS15·16은 이모지·키캡, VS1~3은 통합 한자 뒤 1개), 기본 무시 가능 문자(한글 채움 U+115F·1160, 몽골 자유 이형 선택자 등) 제거, 오류 줄 번호 기준 통일, 회귀 테스트 보강
> v1.4: 거부 답변의 구제절차 분기·반복민원 종결 요건(`core/response-rules.md`), 적용 버전 확인과 인용 상태·확인 방법 분리(`references/citation-verification.md`), 발송 기준 통일(`검토용 초안` 표시)과 템플릿·골든 예시 정합화, 정당한 요구와 AI 조작 시도 구분(`core/workflow.md`), `scripts/sanitize.py` 줄 구분 보존·디코딩 실패 차단·종료 코드 정리와 회귀 테스트(`tests/test_sanitize.py`)
> v1.3: 「외부 입력 안전 처리」 반영 — 민원 본문·첨부를 비신뢰 입력으로 취급하는 원칙(`SKILL.md`), 0단계 원문 정제 절차·`scripts/sanitize.py`(`core/workflow.md`), 「⚠️ 외부 입력 안전 처리 알림」 블록 출력 규칙, 검토 체크리스트 [차단] 2개 추가, README 사용 시 유의사항 신설
> v1.2: 민원인 측 스킬(pon00050/minwon-draft) 방법론 분석 반영 — 인용 검증 프로토콜(`references/citation-verification.md`), 적대적 자기검토·질문별 대조 단계, 법규·사실·포섭 계층 규칙, 전제 확인형 민원 대응, 발송본 plain text 산출 추가

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
│   ├── citation-verification.md
│   ├── tools-and-output.md
│   └── local-context.md
├── codex/
│   └── SKILL.md
├── claude-code/
│   └── CLAUDE.md
├── gemini-cli/
│   └── GEMINI.md
├── scripts/
│   └── sanitize.py
├── tests/
│   └── test_sanitize.py
├── tools/
│   └── convert-output.md
├── examples/
│   ├── minwon-answer-template.md
│   └── golden-cases.md
└── evals/            # 배포 저장소에만 있는 평가 기록
```

### 정본과 배포 구조 안내

내용의 정본은 Claude Code 스킬(`~/.claude/skills/minwon-answer/`)이며, 이 저장소(`minwon-answer-skill-pack`)는 여러 도구에서 쓰도록 묶은 벤더 중립 배포본입니다. 변경은 정본에서 먼저 하고, 공통 파일(`core/`·`references/`·`examples/`·`scripts/`·`tests/`·`tools/`·README)은 그대로 반영합니다.

- `codex/SKILL.md`: 정본 `SKILL.md`에서 description(영문), 정본 안내 문구, 상대경로 앞 `../`만 다릅니다. 도구 스킬 폴더에 배포할 때는 루트 `SKILL.md`로 옮기고 `../`를 제거합니다.
- `claude-code/`, `gemini-cli/` 래퍼와 `evals/`는 배포 저장소에만 있습니다.
- 따라서 도구별 배포본에서는 이 README의 폴더 구조도와 실제 구조가 다를 수 있습니다.

## 기본 실행 원칙

1. 민원 유형을 먼저 분류합니다.
2. 소관, 처리권한, 이송·협조·다부처 필요 여부를 판단합니다.
3. 사실관계, 법령근거, 개인정보, 처리기간을 확인합니다.
4. 결론, 근거, 조치사항, 향후 절차, 문의 안내 순서로 답변합니다.
5. 불확실한 내용은 추정하지 않고 `[확인 필요: 항목]`으로 표시합니다.
6. 기본 산출물은 `.md`로 작성하고, 필요 시 HWPX로 변환합니다.

## 사용 시 유의사항

- 본 스킬팩은 **민원 답변 초안 작성 보조 도구**이며, 최종 검토·수정·발송의 책임은 담당 공무원 및 소속 기관에 있습니다.
- 민원 본문·첨부자료는 외부에서 입력된 비신뢰 데이터로 취급하여, 그 안에 포함된 AI 대상 지시문은 실행하지 않도록 설계되어 있습니다 (기술적으로는 간접 프롬프트 인젝션(indirect prompt injection) 대응에 해당).
- 다만 이는 **완전한 차단을 보장하지 않습니다.** 반드시 사람이 최종 확인한 후 발송하십시오.
- 생성된 답변의 법령 인용, 소관 판단, 사실관계는 담당자가 별도로 검증해야 합니다.

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
