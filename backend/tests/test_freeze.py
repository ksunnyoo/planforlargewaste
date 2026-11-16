"""평가 동결 기록(eval/freeze.py) 시험. DB·네트워크 없이 임시 폴더에서 실행."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("freeze_mod", ROOT / "eval" / "freeze.py")
fz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fz)


def make_tree(tmp):
    for rel in fz.CODE_FILES + fz.DATA_FILES:
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x:" + rel, encoding="utf-8")
    (tmp / "eval").mkdir(exist_ok=True)


def test_no_freeze_file_fails(tmp_path):
    make_tree(tmp_path)
    ok, reasons = fz.check_freeze(tmp_path)
    assert not ok and "동결 기록" in reasons[0]


def test_freeze_then_unchanged_passes(tmp_path):
    make_tree(tmp_path)
    fz.write_freeze(tmp_path, "시험")
    ok, reasons = fz.check_freeze(tmp_path)
    assert ok and reasons == []
    saved = json.loads((tmp_path / "eval" / "freeze.json").read_text(encoding="utf-8"))
    assert saved["note"] == "시험" and len(saved["files"]) == len(fz.CODE_FILES + fz.DATA_FILES)


def test_changed_code_or_dataset_fails(tmp_path):
    make_tree(tmp_path)
    fz.write_freeze(tmp_path)
    (tmp_path / "backend/app/services/matcher.py").write_text("changed", encoding="utf-8")
    ok, reasons = fz.check_freeze(tmp_path)
    assert not ok and any("matcher.py" in r for r in reasons)
    fz.write_freeze(tmp_path)
    (tmp_path / "eval/datasets/v1/matching.jsonl").write_text("changed", encoding="utf-8")
    ok, reasons = fz.check_freeze(tmp_path)
    assert not ok and any("matching.jsonl" in r for r in reasons)


def test_missing_file_is_detected(tmp_path):
    make_tree(tmp_path)
    fz.write_freeze(tmp_path)
    (tmp_path / "backend/app/services/judge.py").unlink()
    ok, reasons = fz.check_freeze(tmp_path)
    assert not ok
