import json
import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from scripts.evaluate_pipeline import (
    evaluate_single_record,
    compute_evaluation_metrics,
    generate_synthetic_mp4_clip,
    _PROJECT_ROOT,
)


@pytest.fixture
def sample_batch():
    batch_path = _PROJECT_ROOT / "data" / "onboarding_batch.json"
    assert batch_path.exists(), f"Batch file not found: {batch_path}"
    with open(batch_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("records", [])


class TestEvaluationPipelineMechanics:
    def test_synthetic_video_generator_validity(self):
        """Synthetic MP4 clip generator should return valid non-empty byte buffer."""
        clip_bytes = generate_synthetic_mp4_clip("test-session-eval-001", num_frames=5)
        assert isinstance(clip_bytes, bytes)
        assert len(clip_bytes) > 500  # valid MP4 container header + frames

    def test_single_record_execution_e2e(self, sample_batch):
        """Single record should evaluate cleanly through all active stages."""
        assert len(sample_batch) > 0
        rec = sample_batch[0]
        res = evaluate_single_record(rec, mode="e2e")

        assert "session_id" in res
        assert "ground_truth" in res
        assert "pipeline_outcome" in res
        assert res["pipeline_outcome"] in ("fast_pass", "hard_reject", "stage3_resolved", "stage4_escalated")
        assert res["total_latency_ms"] >= 0.0
        assert res["stage1_latency_ms"] >= 0.0

    def test_metrics_computation_bounds_and_validity(self, sample_batch):
        """Metrics computation should adhere to strict mathematical bounds (0.0 to 1.0)."""
        # Run small slice for fast unit verification
        slice_records = sample_batch[:10]
        results = [evaluate_single_record(r, mode="decision-only") for r in slice_records]
        metrics = compute_evaluation_metrics(results)

        km = metrics["key_metrics"]
        assert 0.0 <= km["detection_recall_on_bad_cases"] <= 1.0
        assert 0.0 <= km["false_escalation_rate"] <= 1.0
        assert 0.0 <= km["autonomous_resolution_rate"] <= 1.0
        assert 0.0 <= km["overall_accuracy"] <= 1.0

        lp = metrics["latency_profiles_ms"]
        for stage_name, stats in lp.items():
            assert stats["mean"] >= 0.0
            assert stats["median"] >= 0.0
            assert stats["min"] >= 0.0
            assert stats["max"] >= stats["min"]
            assert stats["p95"] >= 0.0

    def test_confusion_matrix_3x4_sum(self, sample_batch):
        """3×4 confusion matrix counts must sum exactly to the number of records evaluated."""
        slice_records = sample_batch[:15]
        results = [evaluate_single_record(r, mode="decision-only") for r in slice_records]
        metrics = compute_evaluation_metrics(results)

        cm = metrics["confusion_matrix_3x4"]
        assert "pass" in cm
        assert "borderline" in cm
        assert "fail" in cm

        total_in_matrix = 0
        expected_cols = {"fast_pass", "hard_reject", "stage3_resolved", "stage4_escalated"}
        for gt_label, row in cm.items():
            assert set(row.keys()) == expected_cols
            total_in_matrix += sum(row.values())

        assert total_in_matrix == len(slice_records)

    def test_evaluation_artifacts_generated(self):
        """Check that the report PNG and JSON artifacts exist and are non-empty."""
        chart_path = _PROJECT_ROOT / "docs" / "phase7_evaluation_report.png"
        json_path = _PROJECT_ROOT / "docs" / "evaluation_results.json"

        assert json_path.exists(), "evaluation_results.json was not created."
        assert json_path.stat().st_size > 100

        assert chart_path.exists(), "phase7_evaluation_report.png was not created."
        assert chart_path.stat().st_size > 1000  # Non-trivial image file
