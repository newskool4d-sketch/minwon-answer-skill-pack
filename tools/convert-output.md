# Markdown to HWPX 변환 지침

## 목적

민원 답변 초안을 Markdown으로 작성한 뒤 같은 폴더에 HWPX 파일을 생성한다.

## 우선순위

1. 사용자 지정 `md_to_hwpx_com.py`
2. 같은 기능의 `to_hwpx_com.py`
3. 변환 불가 시 Markdown만 산출하고 사유 기록

## 현재 확인된 호환 도구

```text
C:\Users\홍주형\claude-code-backup\to_hwpx_com.py
```

이 도구는 `.md`와 `.docx` 입력을 감지하여 HWPX로 변환하며 `-o` 출력 폴더 옵션을 지원한다.

## 실행 예시

```powershell
python "C:\Users\홍주형\claude-code-backup\to_hwpx_com.py" "답변초안.md" -o "출력폴더"
```

## 변환 후 확인

- HWPX 파일이 생성되었는지 확인한다.
- 파일 크기가 0이 아닌지 확인한다.
- 제목, 표, 목록, 끝 표시가 깨지지 않았는지 확인한다.
- 이미지 변환은 지원되지 않을 수 있으므로 텍스트 중심 문서에 사용한다.
