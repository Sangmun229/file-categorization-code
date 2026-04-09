"""
folder_manager.py - 폴더 생성, 파일 이동/복사, 롤백 기능
"""

import shutil
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

from ai_classifier import ClassificationResult, FileGroup
from file_scanner import FileInfo


UNDO_LOG_NAME = "file_classifier_undo.json"


@dataclass
class MoveRecord:
    src: str
    dst: str
    action: str  # "move" | "copy"


@dataclass
class ExecutionResult:
    session_id: str
    output_root: Path
    moved: list[MoveRecord] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    folders_created: list[str] = field(default_factory=list)


class FolderManager:
    def __init__(self, output_base: Path | None = None, copy_mode: bool = False):
        self.output_base = output_base or self._find_desktop()
        self.copy_mode = copy_mode
        self.undo_log = self.output_base / UNDO_LOG_NAME

    def _find_desktop(self) -> Path:
        home = Path.home()
        for candidate in [
            home / "Desktop",
            home / "바탕 화면",
            home / "OneDrive" / "Desktop",
            home / "OneDrive" / "바탕 화면",
        ]:
            if candidate.exists():
                return candidate
        return home

    def execute(self, classification: ClassificationResult) -> ExecutionResult:
        """분류 결과에 따라 폴더를 생성하고 파일을 이동/복사"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_root = self.output_base / f"정리됨_{session_id[:8]}"

        result = ExecutionResult(
            session_id=session_id,
            output_root=output_root,
        )

        # 분류된 그룹 처리
        for group in classification.groups:
            folder_path = output_root / group.folder_name
            self._ensure_dir(folder_path)
            result.folders_created.append(str(folder_path))

            for file_info in group.files:
                self._move_file(file_info, folder_path, result)

        # 분류 안 된 파일
        if classification.uncategorized:
            etc_folder = output_root / "기타"
            self._ensure_dir(etc_folder)
            result.folders_created.append(str(etc_folder))
            for file_info in classification.uncategorized:
                self._move_file(file_info, etc_folder, result)

        # 롤백 로그 저장
        self._save_undo_log(result)

        return result

    def _ensure_dir(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)

    def _move_file(self, file_info: FileInfo, dest_folder: Path,
                   result: ExecutionResult):
        src = file_info.path
        dst = dest_folder / file_info.name

        # 동일 경로 건너뜀
        if src.resolve() == dst.resolve():
            result.skipped.append(str(src))
            return

        # 이름 충돌 해결
        dst = self._resolve_name_conflict(dst)

        try:
            if self.copy_mode:
                shutil.copy2(src, dst)
            else:
                shutil.move(str(src), dst)

            result.moved.append(MoveRecord(
                src=str(src),
                dst=str(dst),
                action="copy" if self.copy_mode else "move",
            ))
            print(f"  {'복사' if self.copy_mode else '이동'}: {src.name} → {dst.parent.name}/")

        except PermissionError:
            result.errors.append(f"권한 없음: {src}")
        except Exception as e:
            result.errors.append(f"{src.name}: {e}")

    def _resolve_name_conflict(self, path: Path) -> Path:
        """파일명 충돌 시 (1), (2) ... 붙여서 반환"""
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        parent = path.parent
        counter = 1
        while True:
            new_path = parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def _save_undo_log(self, result: ExecutionResult):
        """롤백용 로그를 JSON으로 저장"""
        log_data = {
            "session_id": result.session_id,
            "output_root": str(result.output_root),
            "timestamp": datetime.now().isoformat(),
            "copy_mode": self.copy_mode,
            "records": [
                {"src": r.src, "dst": r.dst, "action": r.action}
                for r in result.moved
            ],
        }
        try:
            self.undo_log.write_text(
                json.dumps(log_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"  ⚠️  롤백 로그 저장 실패: {e}")

    def undo_last(self):
        """마지막 작업을 취소하고 파일을 원래 위치로 복원"""
        if not self.undo_log.exists():
            print("취소할 이전 작업이 없습니다.")
            return

        try:
            log_data = json.loads(self.undo_log.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"롤백 로그를 읽을 수 없습니다: {e}")
            return

        records = log_data.get("records", [])
        copy_mode = log_data.get("copy_mode", False)
        timestamp = log_data.get("timestamp", "")
        output_root = Path(log_data.get("output_root", ""))

        print(f"🔄 작업 취소: {timestamp}")
        print(f"   대상: {output_root}")
        print()

        if copy_mode:
            print("복사 모드로 실행된 작업입니다. 복사된 파일을 삭제합니다.")
            confirm = input("계속하시겠습니까? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes", "예", "ㅇ"):
                print("취소되었습니다.")
                return
            # 복사된 파일 삭제
            success = 0
            for rec in records:
                dst = Path(rec["dst"])
                try:
                    if dst.exists():
                        dst.unlink()
                        success += 1
                except Exception as e:
                    print(f"  ⚠️  삭제 실패: {dst.name} ({e})")
        else:
            confirm = input(f"{len(records)}개 파일을 원래 위치로 되돌리겠습니까? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes", "예", "ㅇ"):
                print("취소되었습니다.")
                return
            # 이동된 파일 원복
            success = 0
            for rec in reversed(records):
                src_original = Path(rec["src"])
                dst_current = Path(rec["dst"])
                try:
                    # 원본 폴더가 없으면 재생성
                    src_original.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst_current), src_original)
                    success += 1
                    print(f"  복원: {dst_current.name}")
                except Exception as e:
                    print(f"  ⚠️  복원 실패: {dst_current.name} ({e})")

        # 빈 폴더 정리
        if output_root.exists():
            try:
                self._remove_empty_dirs(output_root)
            except Exception:
                pass

        # 로그 삭제
        self.undo_log.unlink(missing_ok=True)
        print(f"\n✅ {success}개 파일 복원 완료")

    def _remove_empty_dirs(self, path: Path):
        """재귀적으로 빈 폴더 삭제"""
        for child in path.iterdir():
            if child.is_dir():
                self._remove_empty_dirs(child)
        try:
            path.rmdir()  # 비어있을 때만 성공
        except OSError:
            pass
