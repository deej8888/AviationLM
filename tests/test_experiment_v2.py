import json
import runpy
from pathlib import Path

import pytest

from aerolm.data.generate import sha256

runner = runpy.run_path(str(Path(__file__).parents[1] / "scripts/run_v2_experiment.py"))


def test_one_writer_per_experiment_and_lock_releases(tmp_path):
    acquire = runner["acquire_lock"]
    first = acquire(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="Another experiment"):
            acquire(tmp_path)
    finally:
        first.close()
    acquire(tmp_path).close()


def test_dataset_reuse_checks_size_seed_and_content(tmp_path):
    ensure = runner["ensure_data"]
    manifest = ensure(tmp_path, (20, 10, 10), 84)
    assert ensure(tmp_path, (20, 10, 10), 84) == manifest
    with pytest.raises(ValueError, match="split sizes"):
        ensure(tmp_path, (21, 10, 10), 84)
    with pytest.raises(ValueError, match="seed"):
        ensure(tmp_path, (20, 10, 10), 85)
    (tmp_path / "validation.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        ensure(tmp_path, (20, 10, 10), 84)


def test_frozen_selection_rejects_changed_adapter_or_validation_report(tmp_path):
    config, manifest, report = [
        tmp_path / name for name in ("config.toml", "manifest.json", "report.json")
    ]
    weights = tmp_path / "adapter_model.safetensors"
    adapter_files = [tmp_path / "adapter_config.json", tmp_path / "run_manifest.json"]
    for path in (config, manifest, report, weights, *adapter_files):
        path.write_text("fixture")
    selection = {
        "config_sha256": sha256(config),
        "data_manifest_sha256": sha256(manifest),
        "adapter_sha256": sha256(weights),
        "adapter_files": {p.name: sha256(p) for p in adapter_files},
        "validation_reports": {str(report): sha256(report)},
    }
    verify = runner["verify_selection"]
    verify(selection, config, manifest, tmp_path)
    weights.write_text("changed")
    with pytest.raises(ValueError, match="Selection changed"):
        verify(selection, config, manifest, tmp_path)
    weights.write_text("fixture")
    adapter_files[0].write_text("changed")
    with pytest.raises(ValueError, match="metadata changed"):
        verify(selection, config, manifest, tmp_path)
    adapter_files[0].write_text("fixture")
    report.write_text(json.dumps({"changed": True}))
    with pytest.raises(ValueError, match="validation report changed"):
        verify(selection, config, manifest, tmp_path)
