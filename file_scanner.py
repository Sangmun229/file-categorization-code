"""
file_scanner.py - 재귀적 파일 탐색 및 메타데이터 추출
하위 폴더부터 상위 폴더 순으로 파일을 수집합니다.
"""

import os
import mimetypes
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

# 선택적 라이브러리 (없어도 동작)
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


# 건너뛸 폴더/파일 패턴
SKIP_DIRS = {
    "$RECYCLE.BIN", "System Volume Information", ".git", "__pycache__",
    "node_modules", ".venv", "venv", ".idea", ".vscode", "Thumbs.db",
    "정리됨",  # 이미 정리된 폴더
}

SKIP_EXTENSIONS = {
    ".tmp", ".temp", ".lnk", ".url", ".ini", ".db", ".log",
    ".DS_Store", ".localized",
}

# 내용 추출 가능한 텍스트 확장자
TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs",
    ".yaml", ".yml", ".toml", ".cfg", ".conf", ".ini",
    ".sql", ".sh", ".bat", ".ps1", ".r", ".go", ".rs",
}

# 이진 파일 타입별 설명
BINARY_DESCRIPTIONS = {
    ".pdf":  "PDF 문서",
    ".docx": "Word 문서", ".doc": "Word 문서",
    ".xlsx": "Excel 스프레드시트", ".xls": "Excel 스프레드시트",
    ".pptx": "PowerPoint 프레젠테이션", ".ppt": "PowerPoint 프레젠테이션",
    ".hwp":  "한글 문서", ".hwpx": "한글 문서",
    ".jpg":  "이미지", ".jpeg": "이미지", ".png": "이미지",
    ".gif":  "이미지", ".bmp":  "이미지", ".webp": "이미지", ".svg": "이미지",
    ".mp4":  "동영상", ".avi":  "동영상", ".mov": "동영상", ".mkv": "동영상",
    ".mp3":  "오디오", ".wav":  "오디오", ".flac": "오디오",
    ".zip":  "압축 파일", ".rar": "압축 파일", ".7z": "압축 파일",
    ".exe":  "실행 파일", ".msi": "설치 파일",
}

CONTENT_SAMPLE_CHARS = 600  # 내용 샘플 최대 글자 수


@dataclass
class FileInfo:
    path: Path
    name: str
    stem: str          # 확장자 제외 이름
    extension: str     # 소문자 확장자
    size_bytes: int
    modified_at: datetime
    content_sample: str = ""   # 텍스트 내용 앞부분
    type_hint: str = ""        # 파일 유형 힌트
    depth: int = 0             # 원본 폴더 기준 깊이

    def size_str(self) -> str:
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class FileScanner:
    def __init__(self):
        mimetypes.init()

    def scan(self, root: Path) -> list[FileInfo]:
        """
        root 폴더를 재귀 탐색하여 FileInfo 목록 반환.
        하위 폴더 먼저 처리 (bottom-up: topdown=False).
        """
        results: list[FileInfo] = []

        print(f"  📂 스캔: {root}")

        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            current = Path(dirpath)

            # 건너뛸 폴더 필터
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]

            # 현재 폴더 깊이
            try:
                depth = len(current.relative_to(root).parts)
            except ValueError:
                depth = 0

            for filename in filenames:
                filepath = current / filename
                ext = filepath.suffix.lower()

                # 건너뛸 파일 필터
                if ext in SKIP_EXTENSIONS:
                    continue
                if filename.startswith(".") or filename.startswith("~"):
                    continue

                try:
                    stat = filepath.stat()
                except (PermissionError, OSError):
                    continue

                info = FileInfo(
                    path=filepath,
                    name=filename,
                    stem=filepath.stem,
                    extension=ext,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                    depth=depth,
                )

                info.content_sample = self._extract_content(filepath, ext)
                info.type_hint = self._get_type_hint(ext, filepath)

                results.append(info)

        print(f"    → {len(results)}개 파일")
        return results

    def _extract_content(self, filepath: Path, ext: str) -> str:
        """텍스트 파일이면 앞부분 추출, 이진 파일이면 빈 문자열"""
        if ext in TEXT_EXTENSIONS:
            return self._read_text_file(filepath)

        # PDF 내용 추출 시도
        if ext == ".pdf":
            return self._extract_pdf(filepath)

        # docx 내용 추출 시도
        if ext == ".docx":
            return self._extract_docx(filepath)

        return ""

    def _read_text_file(self, filepath: Path) -> str:
        """인코딩 자동 감지 후 텍스트 파일 읽기"""
        try:
            # 먼저 UTF-8 시도
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(CONTENT_SAMPLE_CHARS).strip()
        except Exception:
            pass

        if HAS_CHARDET:
            try:
                raw = filepath.read_bytes()[:2048]
                detected = chardet.detect(raw)
                enc = detected.get("encoding") or "utf-8"
                return raw[:CONTENT_SAMPLE_CHARS].decode(enc, errors="ignore").strip()
            except Exception:
                pass

        try:
            with open(filepath, "r", encoding="cp949", errors="ignore") as f:
                return f.read(CONTENT_SAMPLE_CHARS).strip()
        except Exception:
            return ""

    def _extract_pdf(self, filepath: Path) -> str:
        """PDF 첫 페이지 텍스트 추출 (pypdf 또는 pdfminer)"""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(filepath), strict=False)
            if reader.pages:
                text = reader.pages[0].extract_text() or ""
                return text[:CONTENT_SAMPLE_CHARS].strip()
        except Exception:
            pass

        try:
            from pdfminer.high_level import extract_text
            text = extract_text(str(filepath), maxpages=1) or ""
            return text[:CONTENT_SAMPLE_CHARS].strip()
        except Exception:
            pass

        return ""

    def _extract_docx(self, filepath: Path) -> str:
        """docx 문서 텍스트 추출"""
        try:
            import docx
            doc = docx.Document(str(filepath))
            texts = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(texts)[:CONTENT_SAMPLE_CHARS].strip()
        except Exception:
            return ""

    def _get_type_hint(self, ext: str, filepath: Path) -> str:
        """파일 유형 힌트 문자열 반환"""
        if ext in BINARY_DESCRIPTIONS:
            return BINARY_DESCRIPTIONS[ext]
        mime, _ = mimetypes.guess_type(str(filepath))
        if mime:
            main_type = mime.split("/")[0]
            return {"image": "이미지", "video": "동영상", "audio": "오디오",
                    "text": "텍스트", "application": "문서"}.get(main_type, "")
        return ""
