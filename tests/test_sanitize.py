"""scripts/sanitize.py 회귀 테스트 — 비식별 가상 자료와 표준 라이브러리만 사용한다.

실행: python -I -B tests/test_sanitize.py
"""

import contextlib
import hashlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sanitize.py"
PYCACHE = SCRIPT.parent / "__pycache__"
PYCACHE_EXISTED = PYCACHE.exists()

_spec = importlib.util.spec_from_file_location("sanitize_under_test", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# 특수 문자는 소스에 직접 넣지 않고 코드포인트로 만든다
ZWSP, ZWJ, RLO, LRI = chr(0x200B), chr(0x200D), chr(0x202E), chr(0x2066)
LS, PS, NEL, VT, FF = chr(0x2028), chr(0x2029), chr(0x85), chr(0x0B), chr(0x0C)
NBSP, IDEO_SPACE, BOM_CH, FFFD = chr(0xA0), chr(0x3000), chr(0xFEFF), chr(0xFFFD)
HANGUL_FILLER, HALFWIDTH_FILLER = chr(0x3164), chr(0xFFA0)
COMPAT_HANJA, VS16, HEART = chr(0xF900), chr(0xFE0F), chr(0x2764)
MAN, WOMAN, GIRL, WHITE_FLAG, RAINBOW, FIRE = (chr(c) for c in (0x1F468, 0x1F469, 0x1F467, 0x1F3F3, 0x1F308, 0x1F525))
BLACK_FLAG, CANCEL_TAG = chr(0x1F3F4), chr(0xE007F)
SLIGHT_SMILE, LEFT_RIGHT_ARROW, KEYCAP, COPYRIGHT = chr(0x1F642), chr(0x2194), chr(0x20E3), chr(0xA9)
VS1, VS15 = chr(0xFE00), chr(0xFE0E)


def tag_flag(code):
    return BLACK_FLAG + "".join(chr(0xE0000 + ord(c)) for c in code) + CANCEL_TAG

SAMPLE = f"안녕하세요.\n체험학습 신청 결과를 문의합니다.\t(가상 민원)\n가{NBSP}나{IDEO_SPACE}다 😀 漢字 ①"


def run_cli(*args, cwd=None):
    proc = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), *map(str, args)],
                          capture_output=True, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8")


def last_line(stderr):
    return stderr.strip().splitlines()[-1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SanitizeFunctionTest(unittest.TestCase):
    def test_plain_korean_unchanged(self):
        cleaned, removed, converted, nfc_changed = mod.sanitize(SAMPLE)
        self.assertEqual(cleaned, SAMPLE)
        self.assertEqual((removed, converted, nfc_changed), ([], [], False))

    def test_nfd_hangul_becomes_nfc(self):
        cleaned, removed, _, nfc_changed = mod.sanitize(unicodedata.normalize("NFD", "민원 답변"))
        self.assertEqual(cleaned, "민원 답변")
        self.assertTrue(nfc_changed)
        self.assertEqual(removed, [])

    def test_zero_width_and_bidi_removed(self):
        cleaned, removed, converted, _ = mod.sanitize(f"가{ZWSP}나{RLO}다{LRI}라")
        self.assertEqual(cleaned, "가나다라")
        self.assertEqual([r for _, _, r in removed],
                         ["ZERO WIDTH SPACE", "RIGHT-TO-LEFT OVERRIDE", "LEFT-TO-RIGHT ISOLATE"])
        self.assertEqual(converted, [])

    def test_tag_characters_removed(self):
        hidden = "".join(chr(0xE0000 + ord(c)) for c in "ignore")
        cleaned, removed, _, _ = mod.sanitize("민원" + hidden + "내용")
        self.assertEqual(cleaned, "민원내용")
        self.assertEqual(len(removed), 6)

    def test_variation_selector_supplement_removed_but_vs16_kept(self):
        hidden = chr(0xE0100 + 5) + chr(0xE0100 + 20)
        cleaned, removed, _, _ = mod.sanitize(f"민원 😀{hidden} 끝 {HEART}{VS16}")
        self.assertEqual(cleaned, f"민원 😀 끝 {HEART}{VS16}")
        self.assertEqual([r for _, _, r in removed],
                         ["VARIATION SELECTOR SUPPLEMENT U+E0105", "VARIATION SELECTOR SUPPLEMENT U+E0114"])

    def test_hangul_fillers_removed(self):
        cleaned, removed, _, _ = mod.sanitize(f"가{HANGUL_FILLER}나{HALFWIDTH_FILLER}다")
        self.assertEqual(cleaned, "가나다")
        self.assertEqual([r for _, _, r in removed], ["HANGUL FILLER", "HALFWIDTH HANGUL FILLER"])

    def test_line_and_paragraph_separators_keep_sentences_apart(self):
        text = f"첫 문장입니다.{LS}둘째 문장입니다.{PS}셋째 문단입니다."
        cleaned, removed, converted, _ = mod.sanitize(text)
        self.assertEqual(cleaned, "첫 문장입니다.\n둘째 문장입니다.\n셋째 문단입니다.")
        self.assertNotIn("입니다.둘째", cleaned)
        self.assertEqual(removed, [])
        self.assertEqual([r for _, _, r in converted], ["LINE SEPARATOR", "PARAGRAPH SEPARATOR"])

    def test_nel_vt_ff_become_newlines(self):
        cleaned, removed, converted, _ = mod.sanitize(f"가{NEL}나{VT}다{FF}라")
        self.assertEqual(cleaned, "가\n나\n다\n라")
        self.assertEqual(removed, [])
        self.assertEqual(len(converted), 3)

    def test_converted_breaks_follow_crlf_files(self):
        cleaned, _, _, _ = mod.sanitize(f"가\r\n나{LS}다")
        self.assertEqual(cleaned, "가\r\n나\r\n다")

    def test_line_numbers_count_converted_breaks(self):
        _, removed, converted, _ = mod.sanitize(f"가{LS}나{ZWSP}다\n라{ZWJ}")
        self.assertEqual(converted[0][1], 1)
        self.assertEqual([ln for _, ln, _ in removed], [2, 3])

    def test_other_controls_still_removed(self):
        cleaned, removed, _, _ = mod.sanitize("가\x00나\x1b다")
        self.assertEqual(cleaned, "가나다")
        self.assertEqual([r for _, _, r in removed], ["CONTROL U+0000", "CONTROL U+001B"])

    def test_lone_cr_becomes_newline(self):
        cleaned, removed, converted, _ = mod.sanitize("첫째\r둘째\r셋째")
        self.assertEqual(cleaned, "첫째\n둘째\n셋째")
        self.assertEqual(removed, [])
        self.assertEqual([r for _, _, r in converted], ["CARRIAGE RETURN (LONE CR)"] * 2)

    def test_lone_cr_in_crlf_text_becomes_crlf(self):
        cleaned, _, converted, _ = mod.sanitize("가\r\n나\r다")
        self.assertEqual(cleaned, "가\r\n나\r\n다")
        self.assertEqual(len(converted), 1)

    def test_line_numbers_in_cr_only_text(self):
        _, removed, _, _ = mod.sanitize(f"가\r나\r다{ZWSP}라")
        self.assertEqual([ln for _, ln, _ in removed], [3])

    def test_emoji_zwj_sequences_kept(self):
        text = (f"가족 {MAN}{ZWJ}{WOMAN}{ZWJ}{GIRL}, 무지개 {WHITE_FLAG}{VS16}{ZWJ}{RAINBOW}, "
                f"불꽃 하트 {HEART}{VS16}{ZWJ}{FIRE}")
        cleaned, removed, _, nfc_changed = mod.sanitize(text)
        self.assertEqual(cleaned, text)
        self.assertEqual((removed, nfc_changed), ([], False))

    def test_rgi_subdivision_flag_kept_other_tag_sequences_removed(self):
        scotland, fake = tag_flag("gbsct"), tag_flag("gbxyz")
        cleaned, removed, _, _ = mod.sanitize(f"스코틀랜드 {scotland} 가짜 {fake}")
        self.assertEqual(cleaned, f"스코틀랜드 {scotland} 가짜 {BLACK_FLAG}")
        self.assertEqual(len(removed), 6)

    def test_stray_zwj_still_removed(self):
        for text, expected in ((f"끝 {MAN}{ZWJ}", f"끝 {MAN}"),
                               (f"{MAN}{ZWJ}{ZWJ}{WOMAN}", f"{MAN}{WOMAN}"),
                               (f"가{ZWJ}{MAN}", f"가{MAN}"),
                               (f"{ZWJ}{MAN}", MAN)):
            cleaned, removed, _, _ = mod.sanitize(text)
            self.assertEqual(cleaned, expected)
            self.assertTrue(all(r == "ZERO WIDTH JOINER" for _, _, r in removed))
            self.assertGreaterEqual(len(removed), 1)

    def test_flag_tag_variants_outside_rgi_removed(self):
        scotland = tag_flag("gbsct")
        upper = BLACK_FLAG + "".join(chr(0xE0000 + ord(c)) for c in "GBSCT") + CANCEL_TAG
        no_cancel = BLACK_FLAG + "".join(chr(0xE0000 + ord(c)) for c in "gbsct")
        tail_only = tag_flag("gbsct")[1:]
        for text, expected in ((scotland + chr(0xE0061), scotland), (upper, BLACK_FLAG),
                               (no_cancel, BLACK_FLAG), (tail_only, "")):
            cleaned, removed, _, _ = mod.sanitize(text)
            self.assertEqual(cleaned, expected)
            self.assertTrue(removed)

    def test_cr_edge_cases(self):
        self.assertEqual(mod.sanitize("가\r\r\n나")[0], "가\r\n\r\n나")
        self.assertEqual(mod.sanitize("\r가\r")[0], "\n가\n")

    def test_zwj_between_non_emoji_symbols_removed(self):
        for left, right in ((0x2308, 0x2309), (0x2329, 0x232A)):
            text = f"{chr(left)}{ZWJ}{chr(right)}"
            _, removed, _, _ = mod.sanitize(text)
            self.assertEqual([r for _, _, r in removed], ["ZERO WIDTH JOINER"], text)

    def test_head_shaking_sequence_kept(self):
        text = f"{SLIGHT_SMILE}{ZWJ}{LEFT_RIGHT_ARROW}{VS16}"
        cleaned, removed, _, _ = mod.sanitize(text)
        self.assertEqual((cleaned, removed), (text, []))

    def test_variation_selector_runs_and_misplaced_selectors_removed(self):
        hidden = "".join(chr(0xFE00 + n) for n in (4, 1, 6, 7))
        cleaned, removed, _, _ = mod.sanitize("민원입니다" + hidden)
        self.assertEqual(cleaned, "민원입니다")
        self.assertEqual(len(removed), 4)
        self.assertTrue(all(r.startswith("VARIATION SELECTOR") for _, _, r in removed))
        cleaned, removed, _, _ = mod.sanitize(f"가{VS16}나 {VS15}")
        self.assertEqual(cleaned, "가나 ")
        self.assertEqual(len(removed), 2)

    def test_valid_variation_selectors_kept(self):
        text = f"{HEART}{VS16} 1{VS16}{KEYCAP} {COPYRIGHT}{VS16} 漢{VS1} {HEART}{VS15}"
        cleaned, removed, _, _ = mod.sanitize(text)
        self.assertEqual((cleaned, removed), (text, []))

    def test_default_ignorable_chars_removed(self):
        for cp in (0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x180F, 0x2065, 0xFFF0, 0xFFF8):
            cleaned, removed, _, _ = mod.sanitize(f"가{chr(cp) * 3}나")
            self.assertEqual(cleaned, "가나", hex(cp))
            self.assertEqual(len(removed), 3, hex(cp))

    def test_variation_selector_bases_narrowed(self):
        for text in (f"2026{VS16}년",                  # 숫자 뒤 VS16인데 키캡이 아님
                     f"漢{chr(0xFE03)}",                # 한자 뒤 VS4
                     f"{COMPAT_HANJA}{VS1}"):           # 호환 한자 뒤 VS1
            _, removed, _, _ = mod.sanitize(text)
            self.assertEqual(len(removed), 1, ascii(text))
            self.assertTrue(removed[0][2].startswith("VARIATION SELECTOR"))

    def test_zwj_with_regional_indicators_or_lone_skin_tones_removed(self):
        for left, right in ((0x1F1F0, 0x1F1F7), (0x1F3FB, 0x1F3FC)):
            _, removed, _, _ = mod.sanitize(f"{chr(left)}{ZWJ}{chr(right)}")
            self.assertEqual([r for _, _, r in removed], ["ZERO WIDTH JOINER"])
        handshake = f"{chr(0x1FAF1)}{chr(0x1F3FB)}{ZWJ}{chr(0x1FAF2)}{chr(0x1F3FF)}"
        self.assertEqual(mod.sanitize(handshake)[:2], (handshake, []))

    def test_vs16_skip_boundaries(self):
        self.assertEqual(mod.sanitize(f"가{VS16}{ZWJ}{MAN}")[0], f"가{MAN}")
        self.assertEqual(mod.sanitize(f"{HEART}{VS16}{VS16}{ZWJ}{FIRE}")[0], f"{HEART}{VS16}{FIRE}")

    def test_zwj_and_vs_outside_unicode_tables_removed(self):
        star, white_star, grin = chr(0x2605), chr(0x2606), chr(0x1F600)
        for text, expected in ((f"{star}{ZWJ}{white_star}", f"{star}{white_star}"),   # 공식 ZWJ 요소 아님
                               (f"{grin}{VS16}", grin),                               # 이형 시퀀스 기반 아님
                               (f"{MAN}{VS16}{ZWJ}{WOMAN}", f"{MAN}{WOMAN}")):  # 비공식 결합의 ZWJ도 제거
            cleaned, removed, _, _ = mod.sanitize(text)
            self.assertEqual(cleaned, expected, ascii(text))
            self.assertTrue(removed)

    def test_zwj_group_longer_than_official_maximum_removed(self):
        boy = chr(0x1F466)
        four = f"{MAN}{ZWJ}{WOMAN}{ZWJ}{GIRL}{ZWJ}{boy}{ZWJ}{boy}"
        cleaned, removed, _, _ = mod.sanitize(four)
        self.assertEqual(cleaned, f"{MAN}{WOMAN}{GIRL}{boy}{boy}")
        self.assertEqual(len(removed), 4)
        three = f"{MAN}{ZWJ}{WOMAN}{ZWJ}{GIRL}{ZWJ}{boy}"
        self.assertEqual(mod.sanitize(three)[:2], (three, []))

    def test_emoji_17_sequence_kept_regardless_of_unicodedata_version(self):
        fight_cloud = chr(0x1FAEF)
        text = f"{MAN}{chr(0x1F3FB)}{ZWJ}{fight_cloud}{ZWJ}{MAN}{chr(0x1F3FC)}"
        self.assertEqual(mod.sanitize(text)[:2], (text, []))

    def test_variation_selectors_outside_cjk_standardized_pairs_removed(self):
        # 한국어 민원에 필요 없는 한자 외 표준 이형 표기(CJK 구두점·숫자 0·굽은 따옴표)는 경고와 함께 제거
        for text in (f"가{chr(0x3001)}{VS1}", f"나{chr(0x3002)}{chr(0xFE01)}", f"10{VS1}", f"{chr(0x201C)}{VS1}",
                     f"學{VS1}"):                                         # 표준 이형 표기 기반이 아닌 한자
            _, removed, _, _ = mod.sanitize(text)
            self.assertEqual(len(removed), 1, ascii(text))

    def test_cjk_standardized_variants_checked_by_exact_pair(self):
        only_fe00 = sorted(mod.SVS_CJK[0xFE00] - mod.SVS_CJK.get(0xFE01, frozenset())
                           - mod.SVS_CJK.get(0xFE02, frozenset()))[0]
        kept = f"{chr(only_fe00)}{VS1}"
        self.assertEqual(mod.sanitize(kept)[:2], (kept, []))
        _, removed, _, _ = mod.sanitize(f"{chr(only_fe00)}{chr(0xFE01)}")  # 공식 쌍이 아닌 선택자
        self.assertEqual(len(removed), 1)

    def test_unofficial_combination_of_official_elements_removed(self):
        female, male, eye, rocket = chr(0x2640), chr(0x2642), chr(0x1F441), chr(0x1F680)
        for text in (f"{female}{ZWJ}{male}", f"{eye}{ZWJ}{rocket}", f"{MAN}{ZWJ}{WOMAN}"):
            _, removed, _, _ = mod.sanitize(text)
            self.assertEqual([r for _, _, r in removed], ["ZERO WIDTH JOINER"], ascii(text))

    def test_compatibility_hanja_kept_while_rest_is_normalized(self):
        text = unicodedata.normalize("NFD", "한") + COMPAT_HANJA + unicodedata.normalize("NFD", "글")
        cleaned, removed, _, nfc_changed = mod.sanitize(text)
        self.assertEqual(cleaned, "한" + COMPAT_HANJA + "글")
        self.assertTrue(nfc_changed)
        self.assertEqual(removed, [])
        self.assertEqual(mod.sanitize(COMPAT_HANJA)[0], COMPAT_HANJA)
        self.assertFalse(mod.sanitize(COMPAT_HANJA)[3])


class SanitizeCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.src = self.dir / "원문.txt"
        self.out = self.dir / "정제본.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def write_src(self, data: bytes):
        self.src.write_bytes(data)
        return sha256(self.src)

    def test_clean_file_is_byte_identical_and_exit_0(self):
        data = SAMPLE.replace("\n", "\r\n").encode("utf-8")
        before = self.write_src(data)
        code, stdout, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.out.read_bytes(), data)
        self.assertEqual(stdout, b"")
        self.assertTrue(last_line(stderr).startswith("[정상]"))
        self.assertEqual(sha256(self.src), before)

    def test_invisible_chars_exit_3_with_output(self):
        before = self.write_src(f"민원{ZWSP}내용{RLO}입니다.\n".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 3)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "민원내용입니다.\n")
        self.assertIn("[경고] 비가시 문자 2개 제거됨", stderr)
        self.assertIn("정제본 기준 줄 번호: 1", stderr)
        self.assertTrue(last_line(stderr).startswith("[경고]"))
        self.assertEqual(sha256(self.src), before)

    def test_line_separator_file_exit_0_and_lines_preserved(self):
        self.write_src(f"첫 문장.{LS}둘째 문장.{PS}셋째 문단.".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.out.read_bytes(), "첫 문장.\n둘째 문장.\n셋째 문단.".encode("utf-8"))
        self.assertIn("[안내] 줄·문단 구분 문자 2개를 줄바꿈으로 바꿈", stderr)

    def test_vt_ff_nel_in_crlf_file_become_crlf(self):
        self.write_src(f"가\r\n나{VT}다{FF}라{NEL}마".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.out.read_bytes(), "가\r\n나\r\n다\r\n라\r\n마".encode("utf-8"))

    def test_removed_and_converted_together_exit_3_and_both_reported(self):
        self.write_src(f"가{LS}나{ZWSP}다".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 3)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "가\n나다")
        self.assertIn("[안내] 줄·문단 구분 문자 1개", stderr)
        self.assertIn("[경고] 비가시 문자 1개 제거됨", stderr)

    def test_existing_replacement_char_warns_and_is_kept(self):
        self.write_src(f"첫 줄\n학생 이름 {FFFD}{FFFD} 관련 민원\n".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 3)
        self.assertIn(FFFD * 2, self.out.read_text(encoding="utf-8"))
        self.assertIn("[경고] 대체 문자(U+FFFD) 2개 발견", stderr)
        self.assertIn("정제본 기준 줄 번호: 2", stderr)

    def test_invalid_utf8_exit_1_without_output(self):
        before = self.write_src("정상 문장\n".encode("utf-8") + b"\xff\xfe" + "뒷부분".encode("utf-8"))
        code, stdout, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 1)
        self.assertFalse(self.out.exists())
        self.assertEqual(stdout, b"")
        offset = len("정상 문장\n".encode("utf-8"))
        self.assertIn(f"{offset}바이트 위치(줄 2)", stderr)
        self.assertNotIn(FFFD, stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertIn("[오류] UTF-8로 읽을 수 없는 바이트", stderr)
        self.assertEqual(sha256(self.src), before)

    def test_invalid_utf8_does_not_overwrite_existing_output(self):
        self.write_src(b"abc\x80def")
        self.out.write_text("기존 정제본", encoding="utf-8")
        code, _, _ = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 1)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "기존 정제본")

    def test_invalid_utf8_stdout_mode_writes_nothing(self):
        self.write_src("가".encode("utf-8")[:2])
        code, stdout, stderr = run_cli(self.src)
        self.assertEqual(code, 1)
        self.assertEqual(stdout, b"")
        self.assertIn("UTF-8로 읽을 수 없는 바이트", stderr)

    def test_invalid_utf8_line_number_counts_lone_cr(self):
        self.write_src(b"a\rb\r\xff")
        code, _, stderr = run_cli(self.src)
        self.assertEqual(code, 1)
        self.assertIn("4바이트 위치(줄 3)", stderr)

    def test_emoji_sequences_file_exit_0(self):
        text = f"가족 사진 {MAN}{ZWJ}{WOMAN}{ZWJ}{GIRL} {tag_flag('gbwls')}\n"
        self.write_src(text.encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.out.read_text(encoding="utf-8"), text)
        self.assertIn("[안내] 이모지·이형 표기 결합 문자(ZWJ·지역 깃발 태그·이형 선택자) 8개 보존", stderr)

    def test_kept_variation_selector_is_reported(self):
        self.write_src(f"감사합니다 {HEART}{VS16}\n".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 0, stderr)
        self.assertIn("이형 선택자) 1개 보존", stderr)
        self.assertTrue(last_line(stderr).startswith("[정상]"))

    def test_lone_cr_file_exit_0_with_notice(self):
        self.write_src(b"a\rb")
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.out.read_bytes(), b"a\nb")
        self.assertIn("[안내] 줄·문단 구분 문자 1개", stderr)

    def test_invalid_utf8_line_number_counts_line_separators(self):
        prefix = f"가{LS}나{NEL}다\r\n".encode("utf-8")
        self.write_src(prefix + b"\xff")
        code, _, stderr = run_cli(self.src)
        self.assertEqual(code, 1)
        self.assertIn(f"{len(prefix)}바이트 위치(줄 4)", stderr)

    def test_invalid_utf8_offset_counts_bom(self):
        self.write_src(b"\xef\xbb\xbfab\xff")
        code, _, stderr = run_cli(self.src)
        self.assertEqual(code, 1)
        self.assertIn("5바이트 위치(줄 1)", stderr)

    def test_empty_or_bom_only_input_exit_1(self):
        for data in (b"", b"\xef\xbb\xbf"):
            self.write_src(data)
            code, stdout, stderr = run_cli(self.src, "-o", self.out)
            self.assertEqual(code, 1, data)
            self.assertIn("[오류] 입력 파일이 비어 있음", stderr)
            self.assertFalse(self.out.exists())
            self.assertEqual(stdout, b"")

    def test_output_same_as_input_is_refused(self):
        before = self.write_src(f"민원{ZWSP}원문".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.src)
        self.assertEqual(code, 1)
        self.assertIn("원본과 같음", stderr)
        self.assertEqual(sha256(self.src), before)

    def test_output_same_as_input_via_relative_path_is_refused(self):
        before = self.write_src(f"민원{ZWSP}원문".encode("utf-8"))
        code, _, stderr = run_cli(self.src.name, "-o", self.src.resolve(), cwd=self.dir)
        self.assertEqual(code, 1)
        self.assertIn("원본과 같음", stderr)
        self.assertEqual(sha256(self.src), before)

    def test_missing_input_exit_1_without_traceback(self):
        code, stdout, stderr = run_cli(self.dir / "없는파일.txt", "-o", self.out)
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(stdout, b"")

    def test_usage_error_exit_1_not_2(self):
        code, _, stderr = run_cli()
        self.assertEqual(code, 1)
        self.assertIn("오류", stderr)

    def test_stdout_mode_outputs_nfc_text(self):
        self.write_src(unicodedata.normalize("NFD", "민원 답변\r\n끝").encode("utf-8"))
        code, stdout, stderr = run_cli(self.src)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, "민원 답변\r\n끝".encode("utf-8"))
        self.assertIn("[안내] NFC 정규화", stderr)

    def test_leading_bom_dropped_mid_bom_reported(self):
        self.write_src(b"\xef\xbb\xbf" + f"가{BOM_CH}나".encode("utf-8"))
        code, _, stderr = run_cli(self.src, "-o", self.out)
        self.assertEqual(code, 3)
        self.assertEqual(self.out.read_bytes(), "가나".encode("utf-8"))
        self.assertIn("ZERO WIDTH NO-BREAK SPACE (BOM): 1개", stderr)


class AtomicWriteTest(unittest.TestCase):
    def test_failed_replace_keeps_existing_output_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            src, out = folder / "원문.txt", folder / "정제본.txt"
            src.write_text("민원 원문입니다.\n", encoding="utf-8")
            out.write_text("이전에 검토를 마친 정제본", encoding="utf-8")
            failure = OSError(28, "No space left on device")
            with mock.patch.object(mod.os, "replace", side_effect=failure), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                code = mod.main([str(src), "-o", str(out)])
            self.assertEqual(code, 1)
            self.assertIn("기존 출력 파일은 바꾸지 않았음", err.getvalue())
            self.assertEqual(out.read_text(encoding="utf-8"), "이전에 검토를 마친 정제본")
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["원문.txt", "정제본.txt"])


def tearDownModule():
    if not PYCACHE_EXISTED and PYCACHE.exists():
        raise AssertionError(f"테스트가 {PYCACHE}를 만들었음")


if __name__ == "__main__":
    unittest.main(verbosity=2)
