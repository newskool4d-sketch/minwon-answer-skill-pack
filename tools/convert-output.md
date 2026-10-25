# Markdown to HWPX 변환 지침

> HWPX 변환 절차의 단일 출처(single source) 문서. 다른 파일에서는 이 문서를 참조만 한다.

## 목적

민원 답변 초안을 Markdown으로 작성한 뒤 같은 폴더에 HWPX 파일을 생성한다.

## 우선순위

1. 사용자가 변환기를 직접 지정하면 그 변환기를 사용
2. 기본 변환기 `to_hwpx_com.py` 사용
3. 변환 불가 시 Markdown만 산출하고 사유 기록

## 현재 확인된 변환기

```text
%USERPROFILE%\.claude\to_hwpx_com.py
```

(확인일: 2026-06-11) 이 도구는 `.md`, `.txt`, `.docx`, `.html`, `.csv`, `.xlsx`, `.pdf` 입력을 감지하여 HWPX로 변환하며 `-o` 출력 폴더 옵션을 지원한다. 다른 PC에서는 경로가 다를 수 있으므로 실행 전 존재 여부를 확인한다.

## 실행 예시

```powershell
python "$env:USERPROFILE\.claude\to_hwpx_com.py" "답변초안.md" -o "출력폴더"
```

공문 형식 답변(끝 표시 필요)인 경우:

```powershell
python "$env:USERPROFILE\.claude\to_hwpx_com.py" "답변초안.md" -o "출력폴더" --insert-end-mark
```

## 변환 후 확인

- HWPX 파일이 생성되었는지 확인한다.
- 파일 크기가 0이 아닌지 확인한다.
- 제목, 표, 목록, 끝 표시가 깨지지 않았는지 확인한다.
- 이미지 변환은 지원되지 않을 수 있으므로 텍스트 중심 문서에 사용한다.
