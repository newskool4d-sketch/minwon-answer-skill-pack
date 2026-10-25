#!/usr/bin/env python3
"""민원 원문 정제 스크립트 (외부 입력 안전 처리, 0단계).

비가시 문자(제로폭 문자·양방향 제어문자·이형 선택자 보충·기타 서식 제어문자)를
제거하고 유니코드 NFC 정규화(호환 한자 제외)를 수행한다. 줄·문단 구분 문자
(U+2028·U+2029·NEL·VT·FF·단독 CR)는 지우면 앞뒤 문장이 붙으므로 줄바꿈으로 바꾼다.
이모지 결합(ZWJ)과 이형 선택자는 Unicode 17.0 공식 표에 있는 조합만 남긴다 — ZWJ 묶음은
공식 ZWJ 시퀀스와 요소별 기반 문자가 정확히 같을 때(피부색·VS16 차이는 허용), 깃발 태그는
잉글랜드·스코틀랜드·웨일스 3종, VS15·VS16은 이형 시퀀스 기반 뒤(숫자·#·*는 키캡일 때만),
VS1~3은 통합 한자의 공식 표준 이형 표기 쌍일 때만 남기고 그 밖의 이형 선택자는 제거한다.
남긴 결합 문자의 개수는 보고한다. 기본 무시 가능 문자(한글 채움, 몽골 자유 이형 선택자
등)는 제거한다. 원본 파일은 수정하지 않는다. 제거·변환 내역은 stderr에 보고하므로, 담당자는
경고가 나오면 이를 이상 징후로 보고 원문을 육안 확인한다.

사용법:
    python <스킬 폴더>/scripts/sanitize.py <원문.txt> -o <정제본.txt>

    -o 없이 실행하면 정제본을 stdout으로 낸다. Windows PowerShell 5.1에서 '>'로
    리디렉션하면 인코딩이 바뀌어 내용이 손상되므로 파일 저장은 -o로 한다.

종료 코드:
    0  정상 — 제거·경고 없음 (줄바꿈 변환·NFC 정규화만 적용될 수 있음)
    1  오류 — UTF-8로 읽을 수 없는 입력, 빈 입력, 입력 파일 없음, 출력 경로가 원본과
       같음, 저장 실패, 인자 오류. 정제본을 만들거나 바꾸지 않는다.
    3  경고 — 비가시 문자를 제거했거나 원문에 대체 문자(U+FFFD)가 있음.
       정제본은 만들었으며 원문을 육안 확인한 뒤 사용한다.
    그 밖의 코드(2 등)는 실행 자체가 실패한 것이다(인터프리터가 스크립트를 열지 못함 등).

표준 라이브러리만 사용한다.
"""

import argparse
import codecs
import os
import sys
import tempfile
import unicodedata

EXIT_OK, EXIT_ERROR, EXIT_WARN = 0, 1, 3

# 제거 대상: 제로폭·양방향 제어·기타 비가시 문자 (코드포인트 → 이름)
INVISIBLE = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0x200E: "LEFT-TO-RIGHT MARK",
    0x200F: "RIGHT-TO-LEFT MARK",
    0x202A: "LEFT-TO-RIGHT EMBEDDING",
    0x202B: "RIGHT-TO-LEFT EMBEDDING",
    0x202C: "POP DIRECTIONAL FORMATTING",
    0x202D: "LEFT-TO-RIGHT OVERRIDE",
    0x202E: "RIGHT-TO-LEFT OVERRIDE",
    0x2060: "WORD JOINER",
    0x2061: "FUNCTION APPLICATION",
    0x2062: "INVISIBLE TIMES",
    0x2063: "INVISIBLE SEPARATOR",
    0x2064: "INVISIBLE PLUS",
    0x2066: "LEFT-TO-RIGHT ISOLATE",
    0x2067: "RIGHT-TO-LEFT ISOLATE",
    0x2068: "FIRST STRONG ISOLATE",
    0x2069: "POP DIRECTIONAL ISOLATE",
    0x00AD: "SOFT HYPHEN",
    0x034F: "COMBINING GRAPHEME JOINER",
    0x180E: "MONGOLIAN VOWEL SEPARATOR",
    0x180B: "MONGOLIAN FREE VARIATION SELECTOR ONE",
    0x180C: "MONGOLIAN FREE VARIATION SELECTOR TWO",
    0x180D: "MONGOLIAN FREE VARIATION SELECTOR THREE",
    0x180F: "MONGOLIAN FREE VARIATION SELECTOR FOUR",
    0x115F: "HANGUL CHOSEONG FILLER",
    0x1160: "HANGUL JUNGSEONG FILLER",
    0x17B4: "KHMER VOWEL INHERENT AQ",
    0x17B5: "KHMER VOWEL INHERENT AA",
    0x3164: "HANGUL FILLER",
    0xFFA0: "HALFWIDTH HANGUL FILLER",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE (BOM)",
    0xFFF9: "INTERLINEAR ANNOTATION ANCHOR",
    0xFFFA: "INTERLINEAR ANNOTATION SEPARATOR",
    0xFFFB: "INTERLINEAR ANNOTATION TERMINATOR",
}
# 줄·문단 구분 문자: 내용 구분에 필요하므로 제거하지 않고 줄바꿈으로 바꾼다
LINE_BREAKS = {
    0x000B: "LINE TABULATION (VT)",
    0x000C: "FORM FEED (FF)",
    0x0085: "NEXT LINE (NEL)",
    0x2028: "LINE SEPARATOR",
    0x2029: "PARAGRAPH SEPARATOR",
}
# U+E0000~E0FFF의 무시 가능 문자(태그 문자, 이형 선택자 보충 VS17~256 등):
# 화면에 보이지 않으면서 ASCII나 임의 바이트를 숨겨 실어 나르는 데 악용된다
IGNORABLE_PLANE = range(0xE0000, 0xE1000)
# 기본 무시 가능(Default_Ignorable) 속성의 미할당 코드포인트
IGNORABLE_UNASSIGNED = frozenset([0x2065, *range(0xFFF0, 0xFFF9)])
TAG_RANGE = range(0xE0000, 0xE0080)
VS_SUPPLEMENT = range(0xE0100, 0xE01F0)
# 이모지·이형 표기 판정 표: Unicode 17.0 데이터(emoji-zwj-sequences.txt, emoji-variation-sequences.txt,
# StandardizedVariants.txt)에서 뽑았다(2026-10-25 수집). 표에 없는 결합은 제거하고 경고한다.
ZWJ, VS16, BLACK_FLAG, CANCEL_TAG = 0x200D, 0xFE0F, 0x1F3F4, 0xE007F
SKIN_TONES = range(0x1F3FB, 0x1F400)
VARIATION_SELECTORS = range(0xFE00, 0xFE10)
EMOJI_PRESENTATION_SELECTORS = (0xFE0E, 0xFE0F)
KEYCAP = 0x20E3
# VS15·VS16은 숫자·#·* 뒤에서는 키캡(U+20E3)이 이어질 때만 허용한다
KEYCAP_BASES = frozenset(map(ord, "0123456789#*"))


def _cps(spec):
    """'1F3C3-1F3C4 2640' 같은 16진 표기에서 코드포인트 집합을 만든다."""
    out = set()
    for token in spec.split():
        start, _, end = token.partition("-")
        out.update(range(int(start, 16), int(end or start, 16) + 1))
    return frozenset(out)


def _sequences(spec):
    """'1F468.1F469.1F467' 같은 점 구분 16진 표기에서 기반 문자 시퀀스 집합을 만든다."""
    return frozenset(tuple(int(c, 16) for c in token.split(".")) for token in spec.split())


def _svs_table(spec):
    """'FE00 ::' 줄 다음에 기반 문자 표기가 이어지는 형식에서 {이형 선택자: 기반 문자 집합}을 만든다."""
    table, current = {}, None
    for line in spec.strip().splitlines():
        if "::" in line:
            current = int(line.partition("::")[0], 16)
            line = line.partition("::")[2]
        table[current] = table.get(current, frozenset()) | _cps(line)
    return table


# 공식 ZWJ 시퀀스를 요소별 기반 문자(피부색·VS16 제외)로 줄인 목록 — ZWJ 묶음은 이 중 하나와 정확히 같아야 한다
RGI_ZWJ_BASE_SEQUENCES = _sequences("""
26D3.1F4A5 26F9.2640 26F9.2642 2764.1F525 2764.1FA79 1F344.1F7EB 1F34B.1F7E9 1F3C3.2640
1F3C3.2640.27A1 1F3C3.2642 1F3C3.2642.27A1 1F3C3.27A1 1F3C4.2640 1F3C4.2642 1F3CA.2640
1F3CA.2642 1F3CB.2640 1F3CB.2642 1F3CC.2640 1F3CC.2642 1F3F3.26A7 1F3F3.1F308 1F3F4.2620
1F408.2B1B 1F415.1F9BA 1F426.2B1B 1F426.1F525 1F43B.2744 1F441.1F5E8 1F468.2695 1F468.2696
1F468.2708 1F468.2764.1F468 1F468.2764.1F48B.1F468 1F468.1F33E 1F468.1F373 1F468.1F37C
1F468.1F393 1F468.1F3A4 1F468.1F3A8 1F468.1F3EB 1F468.1F3ED 1F468.1F430.1F468 1F468.1F466
1F468.1F466.1F466 1F468.1F467 1F468.1F467.1F466 1F468.1F467.1F467 1F468.1F468.1F466
1F468.1F468.1F466.1F466 1F468.1F468.1F467 1F468.1F468.1F467.1F466 1F468.1F468.1F467.1F467
1F468.1F469.1F466 1F468.1F469.1F466.1F466 1F468.1F469.1F467 1F468.1F469.1F467.1F466
1F468.1F469.1F467.1F467 1F468.1F4BB 1F468.1F4BC 1F468.1F527 1F468.1F52C 1F468.1F680 1F468.1F692
1F468.1F91D.1F468 1F468.1F9AF 1F468.1F9AF.27A1 1F468.1F9B0 1F468.1F9B1 1F468.1F9B2 1F468.1F9B3
1F468.1F9BC 1F468.1F9BC.27A1 1F468.1F9BD 1F468.1F9BD.27A1 1F468.1FAEF.1F468 1F469.2695
1F469.2696 1F469.2708 1F469.2764.1F468 1F469.2764.1F469 1F469.2764.1F48B.1F468
1F469.2764.1F48B.1F469 1F469.1F33E 1F469.1F373 1F469.1F37C 1F469.1F393 1F469.1F3A4 1F469.1F3A8
1F469.1F3EB 1F469.1F3ED 1F469.1F430.1F469 1F469.1F466 1F469.1F466.1F466 1F469.1F467
1F469.1F467.1F466 1F469.1F467.1F467 1F469.1F469.1F466 1F469.1F469.1F466.1F466 1F469.1F469.1F467
1F469.1F469.1F467.1F466 1F469.1F469.1F467.1F467 1F469.1F4BB 1F469.1F4BC 1F469.1F527 1F469.1F52C
1F469.1F680 1F469.1F692 1F469.1F91D.1F468 1F469.1F91D.1F469 1F469.1F9AF 1F469.1F9AF.27A1
1F469.1F9B0 1F469.1F9B1 1F469.1F9B2 1F469.1F9B3 1F469.1F9BC 1F469.1F9BC.27A1 1F469.1F9BD
1F469.1F9BD.27A1 1F469.1FAEF.1F469 1F46E.2640 1F46E.2642 1F46F.2640 1F46F.2642 1F470.2640
1F470.2642 1F471.2640 1F471.2642 1F473.2640 1F473.2642 1F477.2640 1F477.2642 1F481.2640
1F481.2642 1F482.2640 1F482.2642 1F486.2640 1F486.2642 1F487.2640 1F487.2642 1F575.2640
1F575.2642 1F62E.1F4A8 1F635.1F4AB 1F636.1F32B 1F642.2194 1F642.2195 1F645.2640 1F645.2642
1F646.2640 1F646.2642 1F647.2640 1F647.2642 1F64B.2640 1F64B.2642 1F64D.2640 1F64D.2642
1F64E.2640 1F64E.2642 1F6A3.2640 1F6A3.2642 1F6B4.2640 1F6B4.2642 1F6B5.2640 1F6B5.2642
1F6B6.2640 1F6B6.2640.27A1 1F6B6.2642 1F6B6.2642.27A1 1F6B6.27A1 1F926.2640 1F926.2642
1F935.2640 1F935.2642 1F937.2640 1F937.2642 1F938.2640 1F938.2642 1F939.2640 1F939.2642
1F93C.2640 1F93C.2642 1F93D.2640 1F93D.2642 1F93E.2640 1F93E.2642 1F9B8.2640 1F9B8.2642
1F9B9.2640 1F9B9.2642 1F9CD.2640 1F9CD.2642 1F9CE.2640 1F9CE.2640.27A1 1F9CE.2642
1F9CE.2642.27A1 1F9CE.27A1 1F9CF.2640 1F9CF.2642 1F9D1.2695 1F9D1.2696 1F9D1.2708
1F9D1.2764.1F48B.1F9D1 1F9D1.2764.1F9D1 1F9D1.1F33E 1F9D1.1F373 1F9D1.1F37C 1F9D1.1F384
1F9D1.1F393 1F9D1.1F3A4 1F9D1.1F3A8 1F9D1.1F3EB 1F9D1.1F3ED 1F9D1.1F430.1F9D1 1F9D1.1F4BB
1F9D1.1F4BC 1F9D1.1F527 1F9D1.1F52C 1F9D1.1F680 1F9D1.1F692 1F9D1.1F91D.1F9D1 1F9D1.1F9AF
1F9D1.1F9AF.27A1 1F9D1.1F9B0 1F9D1.1F9B1 1F9D1.1F9B2 1F9D1.1F9B3 1F9D1.1F9BC 1F9D1.1F9BC.27A1
1F9D1.1F9BD 1F9D1.1F9BD.27A1 1F9D1.1F9D1.1F9D2 1F9D1.1F9D1.1F9D2.1F9D2 1F9D1.1F9D2
1F9D1.1F9D2.1F9D2 1F9D1.1FA70 1F9D1.1FAEF.1F9D1 1F9D4.2640 1F9D4.2642 1F9D6.2640 1F9D6.2642
1F9D7.2640 1F9D7.2642 1F9D8.2640 1F9D8.2642 1F9D9.2640 1F9D9.2642 1F9DA.2640 1F9DA.2642
1F9DB.2640 1F9DB.2642 1F9DC.2640 1F9DC.2642 1F9DD.2640 1F9DD.2642 1F9DE.2640 1F9DE.2642
1F9DF.2640 1F9DF.2642 1FAF1.1FAF2
""")
# VS15·VS16을 붙일 수 있는 문자
EMOJI_VS_BASES = _cps("""
23 2A 30-39 A9 AE 203C 2049 2122 2139 2194-2199 21A9-21AA 231A-231B 2328 23CF 23E9-23F3
23F8-23FA 24C2 25AA-25AB 25B6 25C0 25FB-25FE 2600-2604 260E 2611 2614-2615 2618 261D 2620
2622-2623 2626 262A 262E-262F 2638-263A 2640 2642 2648-2653 265F-2660 2663 2665-2666 2668 267B
267E-267F 2692-2697 2699 269B-269C 26A0-26A1 26A7 26AA-26AB 26B0-26B1 26BD-26BE 26C4-26C5 26C8
26CE-26CF 26D1 26D3-26D4 26E9-26EA 26F0-26F5 26F7-26FA 26FD 2702 2705 2708-270D 270F 2712 2714
2716 271D 2721 2728 2733-2734 2744 2747 274C 274E 2753-2755 2757 2763-2764 2795-2797 27A1 27B0
27BF 2934-2935 2B05-2B07 2B1B-2B1C 2B50 2B55 3030 303D 3297 3299 1F004 1F170-1F171 1F17E-1F17F
1F202 1F21A 1F22F 1F237 1F30D-1F30F 1F315 1F31C 1F321 1F324-1F32C 1F336 1F378 1F37D 1F393
1F396-1F397 1F399-1F39B 1F39E-1F39F 1F3A7 1F3AC-1F3AE 1F3C2 1F3C4 1F3C6 1F3CA-1F3CE 1F3D4-1F3E0
1F3ED 1F3F3 1F3F5 1F3F7 1F408 1F415 1F41F 1F426 1F43F 1F441-1F442 1F446-1F449 1F44D-1F44E 1F453
1F46A 1F47D 1F4A3 1F4B0 1F4B3 1F4BB 1F4BF 1F4CB 1F4DA 1F4DF 1F4E4-1F4E6 1F4EA-1F4ED 1F4F7
1F4F9-1F4FB 1F4FD 1F508 1F50D 1F512-1F513 1F549-1F54A 1F550-1F567 1F56F-1F570 1F573-1F579 1F587
1F58A-1F58D 1F590 1F5A5 1F5A8 1F5B1-1F5B2 1F5BC 1F5C2-1F5C4 1F5D1-1F5D3 1F5DC-1F5DE 1F5E1 1F5E3
1F5E8 1F5EF 1F5F3 1F5FA 1F610 1F687 1F68D 1F691 1F694 1F698 1F6AD 1F6B2 1F6B9-1F6BA 1F6BC 1F6CB
1F6CD-1F6CF 1F6E0-1F6E5 1F6E9 1F6F0 1F6F3
""")
# 통합 한자의 표준 이형 표기: 이형 선택자(VS1~3)별 기반 한자. 그 밖의 VS1~14는 제거한다
SVS_CJK = _svs_table("""
FE00 ::
349E 34B9 34BB 34DF 3515 36EE 36FC 3781 382F 3862 387C 38C7 38E3 391C 393A 3A2E 3A6C 3AE4 3B08
3B19 3B49 3B9D 3C18 3C4E 3D33 3D96 3EAC 3EB8 3F1B 3FFC 4008 4018 4039 4046 4096 40E3 412F 4202
4227 42A0 4301 4334 4359 43D5 43D9 440B 446B 452B 455D 4561 456B 45D7 45F9 4635 46BE 46C7 4995
49E6 4A6E 4A76 4AB2 4B33 4BCE 4CCE 4CED 4CF8 4D56 4E0D 4E26 4E32 4E38-4E39 4E3D 4E41 4E82 4E86
4EAE 4EC0 4ECC 4EE4 4F60 4F80 4F86 4F8B 4FAE 4FBB 4FBF 5002 502B 507A 5099 50CF 50DA 50E7 5140
5145 514D 5154 5164 5167-5169 516D 5177 5180 518D 5192 5195 5197 51A4 51AC 51B5 51B7 51C9 51CC
51DC 51DE 51F5 5203 5207 5217 5229 523A-523B 5246 5272 5277 5289 529B 52A3 52B3 52C7 52C9 52D2
52DE 52E4 52F5 52FA 5305-5306 5317 533F 5349 5351 535A 5373 5375 537D 537F 53C3 53CA 53DF 53E5
53EB 53F1 5406 540F 541D 5438 5442 5448 5468 549E 54A2 54BD 54F6 5510 5553 5555 5563 5584 5587
5599 559D 55AB 55B3 55C0 55C2 55E2 5606 5651 5668 5674 56F9 5716-5717 578B 57CE 57F4 580D
5831-5832 5840 585A 585E 58A8 58AC 58B3 58D8 58DF 58EE 58F2 58F7 5906 591A 5922 5944 5948 5951
5954 5962 5973 59D8 59EC 5A1B 5A27 5A62 5A66 5AB5 5B08 5B28 5B3E 5B85 5BC3 5BD8 5BE7 5BEE 5BF3
5BFF 5C06 5C22 5C3F 5C60 5C62 5C64-5C65 5C6E 5C8D 5CC0 5D19 5D43 5D50 5D6B 5D6E 5D7C 5DB2 5DBA
5DE1-5DE2 5DFD 5E28 5E3D 5E69 5E74 5EA6 5EB0 5EB3 5EB6 5EC9-5ECA 5ED2-5ED3 5ED9 5EEC 5EFE 5F04
5F22 5F53 5F62 5F69 5F6B 5F8B 5F9A 5FA9 5FAD 5FCD 5FD7 5FF5 5FF9 6012 601C 6075 6081 6094 60C7
60D8 60E1 6108 6144 6148 614C 614E 6160 6168 617A 618E 6190 61A4 61AF 61B2 61DE 61F2 61F6 6200
6210 621B 622E 6234 625D 62B1 62C9 62CF 62D3-62D4 62FC 62FE 633D 6350 6368 637B 6383 63A0 63A9
63C4-63C5 63E4 641C 6422 6452 6469 6477 647E 649A 649D 64C4 654F 6556 656C 6578 6599 65C5
65E2-65E3 6613 6649 6674 6688 6691 669C 66B4 66C6 66F4 66F8 6700 6717 671B 6721 674E 6753 6756
675E 677B 6785 6797 67F3 67FA 6817 681F 6852 6881 6885 688E 68A8 6914 6942 69A3 69EA 6A02 6A13
6AA8 6AD3 6ADB 6B04 6B21 6B54 6B72 6B77 6B79 6B9F 6BAE 6BBA-6BBB 6C4E 6C67 6C88 6CBF 6CCC-6CCD
6CE5 6D16 6D1B 6D1E 6D34 6D3E 6D41 6D69-6D6A 6D77-6D78 6D85 6DCB 6DDA 6DEA 6DF9 6E1A 6E2F 6E6E
6E9C 6EBA 6EC7 6ECB 6ED1 6EDB 6F0F 6F22-6F23 6F6E 6FC6 6FEB 6FFE 701B 701E 7039 704A 7070 7077
707D 7099 70AD 70C8 70D9 7145 7149 716E 719C 71CE 71D0 7210 721B 7228 722B 7235 7250 7262 7280
7295 72AF 72C0 72FC 732A 7375 737A 7387 738B 73A5 73B2 73DE 7406 7409 7422 7447 745C 7469 7471
7485 7489 7498 74CA 7506 7524 753B 753E 7559 7565 7570 75E2 7610 761D 761F 7642 7669 76CA 76DB
76E7 76F4 7701 771E-771F 7740 774A 778B 77A7 784E 786B 788C 7891 78CA 78CC 78FB 792A 793C 793E
7948-7949 7950 7956 795D-795E 7965 797F 798D-798F 79AE 79CA 79EB 7A1C 7A40 7A4A 7A4F 7A81 7AB1
7ACB 7AEE 7B20 7BC0 7BC6 7BC9 7C3E 7C60 7C7B 7C92 7CBE 7CD2 7CD6 7CE3 7CE7-7CE8 7D00 7D10 7D22
7D2F 7D5B 7D63 7DA0 7DBE 7DC7 7DF4 7E02 7E09 7E37 7E41 7E45 7F3E 7F72 7F79-7F7A 7F85 7F95 7F9A
7FBD 7FFA 8001 8005 8046 8060 806F-8070 807E 808B 80AD 80B2 8103 813E 81D8 81E8 81ED 8201 8204
8218 826F 8279 828B 8291 829D 82B1 82B3 82BD 82E5-82E6 831D 8323 8336 8352-8353 8363 83AD 83BD
83C9-83CA 83CC 83DC 83E7 83EF 83F1 843D 8449 8457 84EE 84F1 84F3 84FC 8516 8564 85CD 85FA 8606
8612 862D 863F 8650 865C 8667 8669 8688 86A9 86E2 870E 8728 876B 8779 8786 87BA 87E1 8801 881F
884C 8860 8863 88C2 88CF 88D7 88DE 88E1 88F8 88FA 8910 8941 8964 8986 898B 8996 8AA0 8AAA 8ABF
8ACB 8AD2 8AD6 8AED 8AF8 8AFE 8B01 8B39 8B58 8B80 8B8A 8C48 8C55 8CAB 8CC1-8CC2 8CC8 8CD3 8D08
8D1B 8D77 8DBC 8DCB 8DEF-8DF0 8ECA 8ED4 8F26 8F2A 8F38 8F3B 8F62 8F9E 8FB0 8FB6 9023 9038 9072
907C 908F 9094 90CE 90DE 90F1 90FD 9111 911B 916A 9199 91B4 91CC 91CF 91D1 9234 9238 9276 927C
92D7-92D8 9304 934A 93F9 9415 958B 95AD 95B7 962E 964B 964D 9675 9678 967C 9686 96A3 96B7-96B8
96C3 96E2-96E3 96F6-96F7 9723 9732 9748 9756 97DB 97E0 97FF 980B 9818 9829 983B 985E 98E2 98EF
98FC 9928-9929 99A7 99C2 99F1 99FE 9A6A 9B12 9B6F 9C40 9C57 9CFD 9D67 9DB4 9DFA 9E1E 9E7F 9E97
9E9F 9EBB 9ECE 9EF9 9EFE 9F05 9F0F 9F16 9F3B 9F43 9F8D-9F8E 9F9C 20122 2051C 20525 2054B 2063A
20804 208DE 20A2C 20B63 214E4 216A8 216EA 219C8 21B18 21D0B 21DE4 21DE6 22183 2219F 22331 226D4
22844 2284A 22B0C 22BF1 2300A 232B8 2335F 23393 2339C 233C3 233D5 2346D 236A3 238A7 23A8D 23AFA
23CBC 23D1E 23ED1 23F5E 23F8E 24263 242EE 243AB 24608 24735 24814 24C36 24C92 24FA1 24FB8 25044
250F2-250F3 25119 25133 25249 2541D 25626 2569A 256C5 2597C 25AA7 25BAB 25C80 25CD0 25F86 261DA
26228 26247 262D9 2633E 264DA 26523 265A8 267A7 267B5 26B3C 26C36 26CD5 26D6B 26F2C 26FB1 270D2
273CA 27667 278AE 27966 27CA8 27ED3 27F2F 285D2 285ED 2872E 28BFA 28D77 29145 291DF 2921A 2940A
29496 295B6 29B30 2A0CE 2A105 2A20E 2A291 2A392 2A600
FE01 ::
3B9D 3EB8 4039 4FAE 50E7 514D 51B5 5207 52C7 52C9 52E4 52FA 5317 5351 537F 5584 5599 559D 5606
585A 5B3E 5BE7 5C6E 5ECA 5F22 6094 614C 614E 618E 61F2 61F6 654F 6674 6691 6717 671B 6885 6A02
6BBA 6D41 6D77 6ECB 6F22 701E 716E 7235 732A 7387 7471 7570 76CA 76F4 771F 774A 788C 78CC 7956
798F 7A40 7BC0 7DF4 8005 8201 8279 82E5 8457 865C 8779 8996 8AAA 8AED 8AF8 8AFE 8B01 8B39 8B8A
8D08 8F38 9038 96E3 9756 97FF 980B 983B 9B12 9F9C 22331 25AA7
FE02 ::
537F 5BE7 618E 61F2 6717 6A02 6BBA 6D41 7DF4 8005 980B 9F9C
""")
# 유니코드 권장(RGI) 지역 깃발 태그 시퀀스는 이 세 가지뿐이며, 그 밖의 태그 문자는 제거한다
RGI_SUBDIVISION_FLAGS = ("gbeng", "gbsct", "gbwls")
# 호환 한자: NFC로 통합 한자에 합쳐지면 독음 구분(예: 樂 낙/락/악)이 사라지므로 정규화하지 않는다
COMPAT_IDEOGRAPHS = (range(0xF900, 0xFB00), range(0x2F800, 0x2FA20))
REPLACEMENT_CHAR = chr(0xFFFD)
# 허용하는 제어문자(줄바꿈·탭·캐리지리턴)
KEEP_CONTROL = {"\n", "\t", "\r"}


def classify(ch):
    """제거 대상이면 사유 문자열, 아니면 None."""
    cp = ord(ch)
    if cp in INVISIBLE:
        return INVISIBLE[cp]
    if cp in IGNORABLE_PLANE:
        if cp in TAG_RANGE:
            return f"TAG CHARACTER U+{cp:05X}"
        if cp in VS_SUPPLEMENT:
            return f"VARIATION SELECTOR SUPPLEMENT U+{cp:05X}"
        return f"IGNORABLE U+{cp:05X}"
    if cp in IGNORABLE_UNASSIGNED:
        return f"IGNORABLE U+{cp:04X}"
    cat = unicodedata.category(ch)
    if cat == "Cc" and ch not in KEEP_CONTROL:
        return f"CONTROL U+{cp:04X}"
    if cat == "Cf":
        return f"FORMAT U+{cp:04X}"
    return None


def variation_selector_reason(text, i):
    """text[i]가 남길 수 없는 이형 선택자면 제거 사유, 아니면 None."""
    cp = ord(text[i])
    if cp not in VARIATION_SELECTORS:
        return None
    base = text[i - 1] if i > 0 else ""
    if (not base or ord(base) in VARIATION_SELECTORS or ord(base) == ZWJ
            or base.isspace() or classify(base)):
        return f"VARIATION SELECTOR WITHOUT BASE U+{cp:04X}"
    b = ord(base)
    if cp in EMOJI_PRESENTATION_SELECTORS:
        if b in EMOJI_VS_BASES and (b not in KEYCAP_BASES or text[i + 1:i + 2] == chr(KEYCAP)):
            return None
    elif b in SVS_CJK.get(cp, ()):
        return None
    return f"VARIATION SELECTOR AFTER UNSUPPORTED BASE U+{cp:04X}"


def kept_variation_selectors(text):
    """정상 기반 뒤라서 남기는 이형 선택자의 위치 집합."""
    return {i for i, ch in enumerate(text)
            if ord(ch) in VARIATION_SELECTORS and variation_selector_reason(text, i) is None}


def _is_break(text, i):
    """sanitize와 같은 기준(CRLF·LF·단독 CR·줄 구분 문자)으로 text[i]가 줄바꿈인지."""
    ch = text[i]
    return ch == "\n" or ord(ch) in LINE_BREAKS or (ch == "\r" and text[i + 1:i + 2] != "\n")


def count_line_breaks(text):
    return sum(1 for i in range(len(text)) if _is_break(text, i))


def line_numbers(text, positions):
    """positions에 있는 위치들의 정제본 기준 줄 번호 목록."""
    wanted, lines, line = set(positions), set(), 1
    for i in range(len(text)):
        if i in wanted:
            lines.add(line)
        if _is_break(text, i):
            line += 1
    return sorted(lines)


def _left_base(text, i):
    """text[i]의 ZWJ 앞 요소의 기반 문자 위치(VS16·피부색은 건너뜀). 없으면 -1."""
    j = i - 1
    if j >= 0 and ord(text[j]) == VS16:
        j -= 1
    if j >= 0 and ord(text[j]) in SKIN_TONES:
        j -= 1
    return j


def _one_element_between(text, a, b):
    """두 ZWJ 사이가 이모지 요소 하나(기반 + 피부색·VS16)뿐인지."""
    middle = text[a + 1:b]
    return 1 <= len(middle) <= 3 and all(ord(c) in SKIN_TONES or ord(c) == VS16 for c in middle[1:])


def emoji_sequence_positions(text):
    """정상 이모지 시퀀스에 속해 보존할 ZWJ·태그 문자의 위치 집합을 돌려준다."""
    flag_tails = [[chr(0xE0000 + ord(c)) for c in code] + [chr(CANCEL_TAG)]
                  for code in RGI_SUBDIVISION_FLAGS]
    keep, groups = set(), []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp == ZWJ and _left_base(text, i) >= 0 and i + 1 < len(text):
            if groups and _one_element_between(text, groups[-1][-1], i):
                groups[-1].append(i)
            else:
                groups.append([i])
        elif cp == BLACK_FLAG:
            for tail in flag_tails:
                if list(text[i + 1:i + 1 + len(tail)]) == tail:
                    keep.update(range(i + 1, i + 1 + len(tail)))
                    break
    # ZWJ 묶음은 요소별 기반 문자가 공식 시퀀스 하나와 정확히 같을 때만 보존한다
    for group in groups:
        bases = (ord(text[_left_base(text, group[0])]),) + tuple(ord(text[z + 1]) for z in group)
        if bases in RGI_ZWJ_BASE_SEQUENCES:
            keep.update(group)
    return keep


def normalize_keep_compat(text):
    """호환 한자를 제외한 구간만 NFC로 정규화한다."""
    parts, buf = [], []
    for ch in text:
        if any(ord(ch) in r for r in COMPAT_IDEOGRAPHS):
            parts.append(unicodedata.normalize("NFC", "".join(buf)))
            parts.append(ch)
            buf = []
        else:
            buf.append(ch)
    parts.append(unicodedata.normalize("NFC", "".join(buf)))
    return "".join(parts)


def sanitize(text: str):
    """(정제본, 제거 목록, 변환 목록, NFC 변경 여부)를 돌려준다.

    목록 항목은 (원문 위치, 정제본 기준 줄 번호, 사유)이다.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    keep = emoji_sequence_positions(text)
    removed = []
    converted = []
    out = []
    line = 1
    for i, ch in enumerate(text):
        lone_cr = ch == "\r" and text[i + 1:i + 2] != "\n"
        if ord(ch) in LINE_BREAKS or lone_cr:
            converted.append((i, line, LINE_BREAKS.get(ord(ch), "CARRIAGE RETURN (LONE CR)")))
            out.append(newline)
            line += 1
            continue
        reason = None if i in keep else (classify(ch) or variation_selector_reason(text, i))
        if reason:
            removed.append((i, line, reason))
        else:
            out.append(ch)
        if ch == "\n":
            line += 1
    joined = "".join(out)
    cleaned = normalize_keep_compat(joined)
    return cleaned, removed, converted, cleaned != joined


class _Parser(argparse.ArgumentParser):
    """인자 오류도 종료 코드 1로 끝낸다(argparse 기본값 2는 인터프리터 실패 코드와 겹친다)."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: 오류: {message}\n")


def _summarize(items, err):
    summary = {}
    for _, _, reason in items:
        summary[reason] = summary.get(reason, 0) + 1
    for reason, n in sorted(summary.items(), key=lambda x: -x[1]):
        err.write(f"  - {reason}: {n}개\n")
    _write_lines(sorted({ln for _, ln, _ in items}), err)


def _write_lines(lines, err):
    err.write(f"  - 정제본 기준 줄 번호: {', '.join(map(str, lines[:30]))}"
              + (" …" if len(lines) > 30 else "") + "\n")


def _write_atomic(path, text):
    """같은 폴더의 임시 파일에 쓴 뒤 바꿔 넣는다. 실패하면 기존 파일은 그대로 둔다."""
    fd, tmp = tempfile.mkstemp(prefix=".sanitize-", suffix=".tmp",
                               dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    err = sys.stderr

    ap = _Parser(description="민원 원문 비가시 문자 제거 + NFC 정규화(호환 한자 제외)")
    ap.add_argument("input", help="원문 텍스트 파일 경로 (UTF-8)")
    ap.add_argument("-o", "--output", help="정제본 저장 경로 (권장, 원본과 같은 경로 불가)")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "rb") as f:
            data = f.read()
    except OSError as e:
        err.write(f"[오류] 입력 파일을 읽을 수 없음: {e}\n")
        return EXIT_ERROR

    base = len(codecs.BOM_UTF8) if data.startswith(codecs.BOM_UTF8) else 0
    if not data[base:]:
        err.write("[오류] 입력 파일이 비어 있음 — 셸 리디렉션 등으로 원본이 비워졌을 수 있으니 원문을 다시 확보할 것\n")
        return EXIT_ERROR
    try:
        text = data[base:].decode("utf-8")
    except UnicodeDecodeError as e:
        offset = base + e.start
        line = count_line_breaks(data[base:offset].decode("utf-8")) + 1
        err.write(f"[오류] UTF-8로 읽을 수 없는 바이트 발견 — 파일 처음부터 {offset}바이트 위치(줄 {line}).\n"
                  "  정제본을 만들지 않았음. 원문을 UTF-8로 다시 저장한 뒤 실행할 것\n")
        return EXIT_ERROR

    if args.output and os.path.exists(args.output) and os.path.samefile(args.input, args.output):
        err.write("[오류] 출력 경로가 원본과 같음 — 원본 보존을 위해 중단\n")
        return EXIT_ERROR

    cleaned, removed, converted, nfc_changed = sanitize(text)

    if args.output:
        try:
            _write_atomic(args.output, cleaned)
        except OSError as e:
            err.write(f"[오류] 정제본을 저장할 수 없음: {e} — 기존 출력 파일은 바꾸지 않았음\n")
            return EXIT_ERROR
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(newline="")
        sys.stdout.write(cleaned)
        sys.stdout.flush()

    if converted:
        err.write(f"[안내] 줄·문단 구분 문자 {len(converted)}개를 줄바꿈으로 바꿈 (내용 보존)\n")
        _summarize(converted, err)
    if nfc_changed:
        err.write("[안내] NFC 정규화로 문자 표현이 바뀜 (조합형 한글 등, 호환 한자는 유지)\n")
    preserved = emoji_sequence_positions(text) | kept_variation_selectors(text)
    if preserved:
        err.write(f"[안내] 이모지·이형 표기 결합 문자(ZWJ·지역 깃발 태그·이형 선택자) {len(preserved)}개 보존 — "
                  "공식 표와 일치하는 결합이지만 개수가 이상하게 많으면 원문을 확인할 것\n")
        _write_lines(line_numbers(text, preserved), err)
    warned = False
    if removed:
        err.write(f"[경고] 비가시 문자 {len(removed)}개 제거됨 — 이상 징후로 보고 원문을 육안 확인할 것\n")
        _summarize(removed, err)
        warned = True
    replacement_lines = [n for n, ln in enumerate(cleaned.split("\n"), 1) if REPLACEMENT_CHAR in ln]
    if replacement_lines:
        err.write(f"[경고] 대체 문자(U+FFFD) {cleaned.count(REPLACEMENT_CHAR)}개 발견 — "
                  "원문이 다른 도구에서 이미 손상됐을 수 있으니 원본 원천 파일을 다시 확보할 것\n")
        _write_lines(replacement_lines, err)
        warned = True
    if warned:
        err.write("[경고] 정제본을 만들었음 — 원문을 육안 확인한 뒤 사용할 것\n")
        return EXIT_WARN
    err.write("[정상] 제거된 비가시 문자 없음\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
