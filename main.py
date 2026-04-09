"""
파일 자동 분류 시스템 - 메인 진입점
사용법:
  python main.py                          # 바탕화면 + 다운로드 폴더 자동 분류
  python main.py --path "C:\폴더"         # 특정 폴더 지정
  python main.py --path "C:\A" "C:\B"    # 여러 폴더 동시 지정
  python main.py --dry-run               # 미리보기만 (실제 이동 없음)
  python main.py --copy                  # 이동 대신 복사
  python main.py --undo                  # 마지막 작업 취소
  python main.py --no-api                # AI 없이 규칙 기반 분류만 사용
"""

import argparse
import sys
import os
from pathlib import Path

from file_scanner import FileScanner
from ai_classifier import AIClassifier
from folder_manager import FolderManager
from reporter import Reporter


def get_default_paths() -> list[Path]:
    """기본 경로: 바탕화면 + 다운로드 폴더"""
    home = Path.home()
    paths = []

    desktop_candidates = [
        home / "Desktop",
        home / "바탕 화면",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "바탕 화면",
    ]
    for p in desktop_candidates:
        if p.exists():
            paths.append(p)
            break

    download_candidates = [
        home / "Downloads",
        home / "다운로드",
    ]
    for p in download_candidates:
        if p.exists():
            paths.append(p)
            break

    return paths


def print_banner():
    print("=" * 60)
    print("   📁 파일 자동 분류 시스템")
    print("   AI 기반 파일 이름 및 내용 분석으로 자동 정리")
    print("=" * 60)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="파일 자동 분류 시스템 - 파일 이름과 내용을 분석하여 자동으로 폴더에 분류합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--path", "-p",
        nargs="+",
        metavar="경로",
        help="분류할 폴더 경로 (여러 개 지정 가능). 미지정 시 바탕화면+다운로드 폴더"
    )
    parser.add_argument(
        "--output", "-o",
        metavar="출력경로",
        help="분류 결과 폴더를 생성할 위치 (기본: 바탕화면)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="실제 파일 이동 없이 분류 결과만 미리보기"
    )
    parser.add_argument(
        "--copy", "-c",
        action="store_true",
        help="파일을 이동하는 대신 복사"
    )
    parser.add_argument(
        "--undo", "-u",
        action="store_true",
        help="마지막 분류 작업을 취소하고 원래 위치로 복원"
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Claude API 없이 규칙 기반 분류만 사용"
    )
    parser.add_argument(
        "--api-key",
        metavar="API_KEY",
        help="Anthropic API 키 (환경변수 ANTHROPIC_API_KEY로도 설정 가능)"
    )
    parser.add_argument(
        "--min-files",
        type=int,
        default=2,
        help="폴더 생성 최소 파일 수 (기본: 2)"
    )

    args = parser.parse_args()

    print_banner()

    # ── 실행 취소 모드 ──────────────────────────────────
    if args.undo:
        manager = FolderManager()
        manager.undo_last()
        return

    # ── 대상 경로 결정 ──────────────────────────────────
    if args.path:
        target_paths = []
        for p in args.path:
            path = Path(p)
            if not path.exists():
                print(f"[오류] 경로를 찾을 수 없습니다: {p}")
                sys.exit(1)
            if not path.is_dir():
                print(f"[오류] 폴더가 아닙니다: {p}")
                sys.exit(1)
            target_paths.append(path)
    else:
        target_paths = get_default_paths()
        if not target_paths:
            print("[오류] 바탕화면/다운로드 폴더를 찾을 수 없습니다.")
            print("  --path 옵션으로 경로를 직접 지정해 주세요.")
            sys.exit(1)
        print(f"기본 경로 사용:")
        for p in target_paths:
            print(f"  📂 {p}")
        print()

    # ── 출력 경로 결정 ──────────────────────────────────
    if args.output:
        output_base = Path(args.output)
    else:
        # 기본: 바탕화면
        home = Path.home()
        for candidate in [home / "Desktop", home / "바탕 화면",
                           home / "OneDrive" / "Desktop", home / "OneDrive" / "바탕 화면"]:
            if candidate.exists():
                output_base = candidate
                break
        else:
            output_base = home

    # ── 파일 스캔 ──────────────────────────────────────
    print("🔍 파일 스캔 중...")
    scanner = FileScanner()
    all_files = []
    for path in target_paths:
        files = scanner.scan(path)
        all_files.extend(files)

    if not all_files:
        print("분류할 파일이 없습니다.")
        return

    print(f"  총 {len(all_files)}개 파일 발견\n")

    # ── AI 분류 ────────────────────────────────────────
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    use_api = not args.no_api and bool(api_key)

    if use_api:
        print("🤖 AI 분류 중 (Claude API)...")
    else:
        if not args.no_api and not api_key:
            print("ℹ️  ANTHROPIC_API_KEY 환경변수가 없습니다. 규칙 기반 분류를 사용합니다.")
            print("   AI 분류를 사용하려면: set ANTHROPIC_API_KEY=your_key_here\n")
        else:
            print("📋 규칙 기반 분류 중...")

    classifier = AIClassifier(api_key=api_key if use_api else None)
    classification = classifier.classify(all_files, min_group_size=args.min_files)

    # ── 결과 미리보기 ──────────────────────────────────
    reporter = Reporter()
    reporter.print_preview(classification, output_base, args.dry_run)

    if args.dry_run:
        print("\n[미리보기 모드] 실제 파일 이동은 수행되지 않았습니다.")
        print("실제 분류를 실행하려면 --dry-run 옵션 없이 다시 실행하세요.")
        return

    # ── 사용자 확인 ────────────────────────────────────
    print()
    action = "복사" if args.copy else "이동"
    confirm = input(f"위 계획대로 파일을 {action}하시겠습니까? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes", "예", "ㅇ"):
        print("취소되었습니다.")
        return

    # ── 파일 이동/복사 ────────────────────────────────
    print(f"\n📦 파일 {action} 중...")
    manager = FolderManager(output_base=output_base, copy_mode=args.copy)
    results = manager.execute(classification)

    # ── 최종 보고서 ────────────────────────────────────
    reporter.print_summary(results)
    print(f"\n✅ 완료! 실행 취소는 'python main.py --undo' 를 사용하세요.")


if __name__ == "__main__":
    main()
