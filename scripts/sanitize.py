#!/usr/bin/env python3
"""민원 원문 정제 스크립트 (외부 입력 안전 처리, 0단계).

비가시 문자(제로폭 문자·양방향 제어문자·기타 서식 제어문자)를 제거하고
유니코드 NFC 정규화를 수행한다. 제거된 문자가 있으면 그 종류·개수·위치를
stderr에 보고하므로, 담당자는 이를 이상 징후로 보고 원문을 육안 확인한다.

사용법:
    python3 scripts/sanitize.py 민원원문.txt            # 정제 결과를 stdout으로
    python3 scripts/sanitize.py 민원원문.txt -o 정제본.txt

표준 라이브러리만 사용한다.
"""

import argparse
import sys
import unicodedata

# 제거 대상: 제로폭·양방향 제어·기타 비가시 서식 문자
INVISIBLE = {
    "​": "ZERO WIDTH SPACE",
    "‌": "ZERO WIDTH NON-JOINER",
    "‍": "ZERO WIDTH JOINER",
    "‎": "LEFT-TO-RIGHT MARK",
    "‏": "RIGHT-TO-LEFT MARK",
    " ": "LINE SEPARATOR",
    " ": "PARAGRAPH SEPARATOR",
    "‪": "LEFT-TO-RIGHT EMBEDDING",
    "‫": "RIGHT-TO-LEFT EMBEDDING",
    "‬": "POP DIRECTIONAL FORMATTING",
    "‭": "LEFT-TO-RIGHT OVERRIDE",
    "‮": "RIGHT-TO-LEFT OVERRIDE",
    "⁠": "WORD JOINER",
    "⁡": "FUNCTION APPLICATION",
    "⁢": "INVISIBLE TIMES",
    "⁣": "INVISIBLE SEPARATOR",
    "⁤": "INVISIBLE PLUS",
    "⁦": "LEFT-TO-RIGHT ISOLATE",
    "⁧": "RIGHT-TO-LEFT ISOLATE",
    "⁨": "FIRST STRONG ISOLATE",
    "⁩": "POP DIRECTIONAL ISOLATE",
    "­": "SOFT HYPHEN",
    "͏": "COMBINING GRAPHEME JOINER",
    "᠎": "MONGOLIAN VOWEL SEPARATOR",
    "﻿": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "￹": "INTERLINEAR ANNOTATION ANCHOR",
    "￺": "INTERLINEAR ANNOTATION SEPARATOR",
    "￻": "INTERLINEAR ANNOTATION TERMINATOR",
}
# 유니코드 태그 문자 블록(U+E0000~E007F): ASCII를 숨겨 실어 나르는 데 악용됨
TAG_RANGE = range(0xE0000, 0xE0080)
# 허용하는 제어문자(줄바꿈·탭·캐리지리턴)
KEEP_CONTROL = {"\n", "\t", "\r"}


def classify(ch):
    """제거 대상이면 사유 문자열, 아니면 None."""
    if ch in INVISIBLE:
        return INVISIBLE[ch]
    cp = ord(ch)
    if cp in TAG_RANGE:
        return f"TAG CHARACTER U+{cp:05X}"
    cat = unicodedata.category(ch)
    if cat == "Cc" and ch not in KEEP_CONTROL:
        return f"CONTROL U+{cp:04X}"
    if cat == "Cf":
        return f"FORMAT U+{cp:04X}"
    return None


def sanitize(text: str):
    removed = []  # (index, line, reason)
    out = []
    line = 1
    for i, ch in enumerate(text):
        reason = classify(ch)
        if reason:
            removed.append((i, line, reason))
        else:
            out.append(ch)
        if ch == "\n":
            line += 1
    cleaned = unicodedata.normalize("NFC", "".join(out))
    return cleaned, removed


def main() -> int:
    ap = argparse.ArgumentParser(description="민원 원문 비가시 문자 제거 + NFC 정규화")
    ap.add_argument("input", help="원문 텍스트 파일 경로 (UTF-8)")
    ap.add_argument("-o", "--output", help="정제본 저장 경로 (생략 시 stdout)")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8-sig", errors="replace") as f:
        text = f.read()

    cleaned, removed = sanitize(text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(cleaned)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(cleaned)

    err = sys.stderr
    err.reconfigure(encoding="utf-8")
    if removed:
        summary = {}
        for _, _, reason in removed:
            summary[reason] = summary.get(reason, 0) + 1
        err.write(f"[경고] 비가시 문자 {len(removed)}개 제거됨 — 이상 징후로 보고 원문을 육안 확인할 것\n")
        for reason, n in sorted(summary.items(), key=lambda x: -x[1]):
            err.write(f"  - {reason}: {n}개\n")
        lines = sorted({ln for _, ln, _ in removed})
        err.write(f"  - 발견 줄 번호: {', '.join(map(str, lines[:30]))}"
                  + (" …" if len(lines) > 30 else "") + "\n")
        return 2
    err.write("[정상] 제거된 비가시 문자 없음 (NFC 정규화만 적용)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
