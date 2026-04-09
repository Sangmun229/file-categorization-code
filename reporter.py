"""
reporter.py - 분류 결과 미리보기 및 완료 보고서 출력
"""

from pathlib import Path
from datetime import datetime

from ai_classifier import ClassificationResult
from folder_manager import ExecutionResult


class Reporter:

    def print_preview(self, classification: ClassificationResult,
                      output_base: Path, dry_run: bool = False):
        """분류 계획을 트리 형식으로 출력"""
        total_files = sum(len(g.files) for g in classification.groups)
        total_files += len(classification.uncategorized)

        print("─" * 55)
        mode_label = "[미리보기]" if dry_run else "[분류 계획]"
        print(f"{mode_label} 총 {total_files}개 파일 → {len(classification.groups)}개 폴더")
        print("─" * 55)
        print()

        date_str = datetime.now().strftime("%Y%m%d")
        output_root_name = f"정리됨_{date_str}"
        print(f"📂 {output_base / output_root_name}")

        for group in classification.groups:
            file_count = len(group.files)
            print(f"   ├── 📁 {group.folder_name}/  ({file_count}개)")
            for i, f in enumerate(group.files[:5]):
                connector = "│   └──" if i == min(4, file_count - 1) else "│   ├──"
                size_str = f.size_str()
                print(f"   {connector} {f.name}  [{size_str}]")
            if file_count > 5:
                print(f"   │   └── ... 외 {file_count - 5}개")
            print("   │")

        if classification.uncategorized:
            count = len(classification.uncategorized)
            print(f"   └── 📁 기타/  ({count}개)")
            for i, f in enumerate(classification.uncategorized[:3]):
                connector = "       └──" if i == min(2, count - 1) else "       ├──"
                print(f"   {connector} {f.name}")
            if count > 3:
                print(f"       └── ... 외 {count - 3}개")
        else:
            # 마지막 그룹의 연결선을 └── 로 수정하기 위해 아무것도 출력 안 함
            pass

        print()
        print("─" * 55)

    def print_summary(self, result: ExecutionResult):
        """실행 완료 후 요약 출력"""
        print()
        print("─" * 55)
        print("📊 실행 결과 요약")
        print("─" * 55)

        moved = len(result.moved)
        skipped = len(result.skipped)
        errors = len(result.errors)
        folders = len(result.folders_created)

        print(f"  ✅ 처리 완료: {moved}개 파일")
        if skipped:
            print(f"  ⏭️  건너뜀:   {skipped}개 파일")
        if errors:
            print(f"  ❌ 오류:     {errors}개 파일")
            for err in result.errors:
                print(f"     - {err}")

        print(f"  📁 생성 폴더: {folders}개")
        print(f"  📂 저장 위치: {result.output_root}")
        print("─" * 55)
