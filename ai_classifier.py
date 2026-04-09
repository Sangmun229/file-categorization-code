"""
ai_classifier.py - 파일 분류 엔진
Claude API를 사용하거나, API 없이 규칙 기반으로 파일을 분류합니다.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

from file_scanner import FileInfo


@dataclass
class FileGroup:
    """같은 카테고리로 분류된 파일 그룹"""
    folder_name: str        # 생성될 폴더 이름
    description: str        # 카테고리 설명
    files: list[FileInfo] = field(default_factory=list)


@dataclass
class ClassificationResult:
    groups: list[FileGroup]
    uncategorized: list[FileInfo]  # 분류되지 않은 파일


# ── 규칙 기반 분류 테이블 ────────────────────────────────────────────────────

RULE_CATEGORIES = {
    "이미지_사진": {
        "extensions": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
                       ".tiff", ".tif", ".heic", ".heif", ".raw", ".cr2", ".nef"},
        "keywords": ["photo", "image", "img", "pic", "사진", "이미지", "스크린샷", "screenshot"],
    },
    "동영상": {
        "extensions": {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv",
                       ".webm", ".m4v", ".3gp", ".ts"},
        "keywords": ["video", "movie", "clip", "영상", "동영상", "녹화"],
    },
    "음악_오디오": {
        "extensions": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma",
                       ".m4a", ".opus", ".aiff"},
        "keywords": ["music", "audio", "song", "음악", "노래", "오디오"],
    },
    "압축_아카이브": {
        "extensions": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
                       ".xz", ".zst", ".cab"},
        "keywords": ["archive", "backup", "압축", "백업"],
    },
    "설치_프로그램": {
        "extensions": {".exe", ".msi", ".msix", ".appx", ".dmg", ".pkg", ".deb", ".rpm"},
        "keywords": ["setup", "install", "installer", "설치"],
    },
    "개발_코드": {
        "extensions": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h",
                       ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
                       ".sh", ".bat", ".ps1", ".r", ".sql", ".html", ".css"},
        "keywords": ["code", "script", "project", "코드", "스크립트", "프로젝트",
                     "개발", "프로그램"],
    },
    "문서_보고서": {
        "extensions": {".pdf", ".docx", ".doc", ".hwp", ".hwpx", ".odt",
                       ".rtf", ".pages"},
        "keywords": ["report", "document", "proposal", "보고서", "제안서",
                     "기획서", "계획서", "문서", "레포트", "논문", "계약서",
                     "specification", "spec", "명세"],
    },
    "스프레드시트_데이터": {
        "extensions": {".xlsx", ".xls", ".csv", ".ods", ".numbers", ".tsv"},
        "keywords": ["data", "sheet", "table", "spreadsheet", "데이터",
                     "표", "통계", "분석", "매출", "예산", "회계"],
    },
    "프레젠테이션": {
        "extensions": {".pptx", ".ppt", ".odp", ".key"},
        "keywords": ["presentation", "slide", "deck", "발표", "슬라이드",
                     "프레젠테이션"],
    },
    "전자책_학습자료": {
        "extensions": {".epub", ".mobi", ".azw3"},
        "keywords": ["book", "lecture", "study", "교재", "강의", "학습",
                     "강좌", "course", "tutorial", "가이드", "manual"],
    },
    "영수증_금융": {
        "extensions": set(),
        "keywords": ["receipt", "invoice", "bill", "payment", "영수증",
                     "청구서", "계산서", "세금계산서", "이체", "입금",
                     "거래내역", "카드", "통장"],
    },
    "설정_환경파일": {
        "extensions": {".json", ".yaml", ".yml", ".toml", ".env", ".cfg",
                       ".conf", ".config", ".xml", ".ini"},
        "keywords": ["config", "setting", "env", "설정", "환경변수"],
    },
}

# 키워드 분류 가중치
KEYWORD_WEIGHT = 2
EXTENSION_WEIGHT = 3


class AIClassifier:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.use_api = bool(api_key)

    def classify(self, files: list[FileInfo],
                 min_group_size: int = 2) -> ClassificationResult:
        """파일 목록을 분류하여 ClassificationResult 반환"""

        if self.use_api:
            try:
                return self._classify_with_api(files, min_group_size)
            except Exception as e:
                print(f"  ⚠️  AI API 오류: {e}")
                print("  규칙 기반 분류로 전환합니다...\n")

        return self._classify_with_rules(files, min_group_size)

    # ── 규칙 기반 분류 ────────────────────────────────────────────────────────

    def _classify_with_rules(self, files: list[FileInfo],
                              min_group_size: int) -> ClassificationResult:
        """확장자 + 키워드 규칙으로 분류"""
        scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for file in files:
            file_id = str(file.path)
            search_text = (file.stem + " " + file.content_sample).lower()

            for category, rules in RULE_CATEGORIES.items():
                # 확장자 매칭
                if file.extension in rules["extensions"]:
                    scores[file_id][category] += EXTENSION_WEIGHT

                # 키워드 매칭
                for kw in rules["keywords"]:
                    if kw.lower() in search_text:
                        scores[file_id][category] += KEYWORD_WEIGHT

        # 각 파일을 최고 점수 카테고리에 배정
        assignments: dict[str, list[FileInfo]] = defaultdict(list)
        uncategorized: list[FileInfo] = []

        for file in files:
            file_id = str(file.path)
            cat_scores = scores[file_id]
            if cat_scores:
                best_cat = max(cat_scores, key=cat_scores.__getitem__)
                assignments[best_cat].append(file)
            else:
                uncategorized.append(file)

        # min_group_size 미만이면 기타로
        groups = []
        small_groups: list[FileInfo] = []

        for category, group_files in assignments.items():
            if len(group_files) >= min_group_size:
                groups.append(FileGroup(
                    folder_name=category,
                    description=f"{category} 관련 파일",
                    files=group_files,
                ))
            else:
                small_groups.extend(group_files)

        uncategorized.extend(small_groups)

        # 추가로 파일명 유사도 기반 소그룹 생성
        extra_groups = self._cluster_by_name_similarity(uncategorized, min_group_size)
        groups.extend(extra_groups["groups"])
        uncategorized = extra_groups["remaining"]

        # 알파벳/날짜 순 정렬
        groups.sort(key=lambda g: g.folder_name)
        return ClassificationResult(groups=groups, uncategorized=uncategorized)

    def _cluster_by_name_similarity(
        self, files: list[FileInfo], min_group_size: int
    ) -> dict:
        """파일명의 공통 접두사/토큰으로 추가 그룹 생성"""
        if not files:
            return {"groups": [], "remaining": []}

        # 파일명을 토큰으로 분리
        def tokenize(stem: str) -> set[str]:
            tokens = re.split(r"[\s_\-\.]+", stem.lower())
            return {t for t in tokens if len(t) >= 3}

        token_to_files: dict[str, list[FileInfo]] = defaultdict(list)
        for file in files:
            for token in tokenize(file.stem):
                token_to_files[token].append(file)

        assigned: set[str] = set()
        new_groups: list[FileGroup] = []

        for token, token_files in sorted(
            token_to_files.items(), key=lambda x: -len(x[1])
        ):
            unassigned = [f for f in token_files if str(f.path) not in assigned]
            if len(unassigned) >= min_group_size:
                folder_name = f"관련_{token}"
                new_groups.append(FileGroup(
                    folder_name=folder_name,
                    description=f"'{token}' 관련 파일",
                    files=unassigned,
                ))
                for f in unassigned:
                    assigned.add(str(f.path))

        remaining = [f for f in files if str(f.path) not in assigned]
        return {"groups": new_groups, "remaining": remaining}

    # ── Claude API 기반 분류 ──────────────────────────────────────────────────

    def _classify_with_api(self, files: list[FileInfo],
                            min_group_size: int) -> ClassificationResult:
        """Claude API를 사용하여 파일을 의미 기반으로 분류"""
        import urllib.request

        # 파일 정보를 간략하게 직렬화
        file_summaries = []
        for i, f in enumerate(files):
            summary = {
                "id": i,
                "name": f.name,
                "type": f.type_hint or f.extension,
                "content_preview": f.content_sample[:200] if f.content_sample else "",
            }
            file_summaries.append(summary)

        # API는 배치로 처리 (최대 100개씩)
        batch_size = 80
        all_assignments: dict[int, str] = {}
        category_descriptions: dict[str, str] = {}

        for batch_start in range(0, len(file_summaries), batch_size):
            batch = file_summaries[batch_start:batch_start + batch_size]
            batch_result = self._api_classify_batch(batch)
            all_assignments.update({
                batch_start + k: v for k, v in batch_result["assignments"].items()
            })
            category_descriptions.update(batch_result["descriptions"])

        # assignments → FileGroup 변환
        cat_to_files: dict[str, list[FileInfo]] = defaultdict(list)
        uncategorized: list[FileInfo] = []

        for i, file in enumerate(files):
            cat = all_assignments.get(i, "기타")
            if cat == "기타":
                uncategorized.append(file)
            else:
                cat_to_files[cat].append(file)

        groups = []
        for cat, cat_files in cat_to_files.items():
            if len(cat_files) >= min_group_size:
                groups.append(FileGroup(
                    folder_name=cat,
                    description=category_descriptions.get(cat, ""),
                    files=cat_files,
                ))
            else:
                uncategorized.extend(cat_files)

        groups.sort(key=lambda g: g.folder_name)
        return ClassificationResult(groups=groups, uncategorized=uncategorized)

    def _api_classify_batch(self, file_summaries: list[dict]) -> dict:
        """단일 배치를 Claude API로 분류"""
        import urllib.request

        prompt = f"""다음 파일 목록을 분석하여 의미적으로 관련된 것끼리 분류해 주세요.

파일 목록 (JSON):
{json.dumps(file_summaries, ensure_ascii=False, indent=2)}

규칙:
1. 파일 이름과 내용 미리보기를 모두 참고하여 분류하세요.
2. 카테고리 이름은 한국어로, 짧고 직관적으로 (예: "프로젝트_보고서", "이미지_사진")
3. 관련 없는 파일은 "기타"로 분류
4. 비슷한 주제/목적의 파일은 같은 카테고리로

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "assignments": {{"<파일 id>": "<카테고리명>", ...}},
  "descriptions": {{"<카테고리명>": "<한 줄 설명>", ...}}
}}"""

        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        text = data["content"][0]["text"].strip()
        # JSON 코드블록 제거
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

        parsed = json.loads(text)
        # id가 문자열로 올 수 있으므로 int 변환
        assignments = {int(k): v for k, v in parsed.get("assignments", {}).items()}
        return {
            "assignments": assignments,
            "descriptions": parsed.get("descriptions", {}),
        }
