# 📁 파일 자동 분류 시스템

파일 이름과 내용을 분석하여 관련된 파일끼리 자동으로 폴더에 분류하는 Python 프로그램입니다.

---

## 📦 파일 구성

```
file_classifier/
├── main.py           # 메인 실행 파일
├── file_scanner.py   # 재귀 파일 탐색 및 메타데이터 추출
├── ai_classifier.py  # 파일 분류 엔진 (규칙 기반 + Claude AI)
├── folder_manager.py # 폴더 생성 및 파일 이동/복사, 롤백
└── reporter.py       # 결과 미리보기 및 완료 보고서 출력
```

---

## ⚙️ 설치 (최초 1회)

Python 3.8 이상이 필요합니다.

```cmd
pip install chardet
```

PDF/Word 파일 내용까지 분석하려면 (선택):
```cmd
pip install pypdf python-docx
```

---

## 🚀 실행 방법

### 기본 실행 (바탕화면 + 다운로드 폴더 자동 정리)
```cmd
python main.py
```

### 특정 폴더 지정
```cmd
python main.py --path "C:\Users\홍길동\Documents"
```

### 여러 폴더 동시 지정
```cmd
python main.py --path "C:\Users\홍길동\Documents" "C:\Users\홍길동\Desktop"
```

### 실제 이동 없이 미리보기만 확인
```cmd
python main.py --dry-run
```

### 파일을 이동 대신 복사
```cmd
python main.py --copy
```

### 마지막 작업 취소 (원래 위치로 복원)
```cmd
python main.py --undo
```

### Claude AI API 사용 (더 정확한 분류)
```cmd
set ANTHROPIC_API_KEY=your_api_key_here
python main.py
```

또는 실행 시 직접 지정:
```cmd
python main.py --api-key sk-ant-xxxx
```

### AI 없이 규칙 기반 분류만 사용
```cmd
python main.py --no-api
```

---

## 📁 분류 결과 예시

실행 후 바탕화면에 아래와 같은 구조로 생성됩니다:

```
바탕화면/
└── 정리됨_20260409/
    ├── 문서_보고서/       ← PDF, Word, 한글 문서
    ├── 이미지_사진/       ← jpg, png, gif 등
    ├── 스프레드시트_데이터/ ← Excel, CSV 등
    ├── 개발_코드/         ← py, js, java 등
    ├── 프레젠테이션/      ← PowerPoint 등
    ├── 압축_아카이브/     ← zip, rar 등
    ├── 영수증_금융/       ← 영수증, 청구서 관련
    └── 기타/              ← 분류되지 않은 파일
```

---

## 🔧 옵션 전체 목록

| 옵션 | 설명 |
|------|------|
| `--path 경로 [경로...]` | 분류할 폴더 (기본: 바탕화면+다운로드) |
| `--output 경로` | 결과 폴더 생성 위치 (기본: 바탕화면) |
| `--dry-run` | 미리보기만 (실제 이동 없음) |
| `--copy` | 이동 대신 복사 |
| `--undo` | 마지막 작업 취소 |
| `--no-api` | AI 없이 규칙 기반 분류 |
| `--api-key KEY` | Anthropic API 키 직접 입력 |
| `--min-files N` | 폴더 생성 최소 파일 수 (기본: 2) |

---

## ⚠️ 주의사항

- 실행 전 `--dry-run`으로 반드시 미리보기 확인을 권장합니다.
- 중요한 파일은 백업 후 실행하세요.
- `--undo`는 가장 마지막 1회 작업만 취소 가능합니다.
- 시스템 파일 및 숨김 파일(`.`으로 시작)은 자동으로 건너뜁니다.
