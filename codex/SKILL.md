---
name: minwon-answer
description: Draft, review, and finalize Korean public complaint responses for education-office and public-sector workflows. Use when the user asks for 민원 답변, 고충민원, 국민신문고, 제안, 예산낭비신고, 제도개선, 민원·정책 질의응답, 국민생각함, 선순환 이슈카드 handling, including jurisdiction checks, legal basis review, routing, Markdown output, and optional HWPX conversion.
---

# Minwon Answer

Use this skill for Korean public complaint response work.

## Load Order

1. Read `../core/workflow.md`.
2. Read `../core/response-rules.md`.
3. Read `../core/quality-checklist.md`.
4. Load only the relevant reference file from `../references/`.
5. Before drafting, read `../examples/golden-cases.md` for tone and structure.
6. Load `../references/local-context.md` only when institution-specific jurisdiction or local conventions matter.

## Required Behavior

- Respond in Korean unless the user asks otherwise.
- Classify the complaint type before drafting.
- Check jurisdiction, routing, multi-agency handling, cooperation, deadlines, privacy, and legal basis.
- Use `[확인 필요: 항목]` for unsupported facts.
- Use `korean-law-mcp` for legal review when available.
- Use `insane-search` for current search when available.
- Use `deep-research` for complex research when available.
- When a tool is unavailable, follow the fallback table in `../references/tools-and-output.md`.
- Produce Markdown by default.
- Convert Markdown to HWPX in the same output folder when requested and a converter is available.

## Output Shape

For most tasks, produce:

1. `민원 요지`
2. `처리 판단`
3. `답변 초안`
4. `검토 체크리스트`
5. `확인 필요 사항`

For final sending drafts, remove internal notes and unresolved checklist items.
