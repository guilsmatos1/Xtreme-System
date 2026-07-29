import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "process_issue.py"
SPEC = importlib.util.spec_from_file_location("process_issue", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_determine_variant_reads_markdown_metadata():
    assert MODULE.determine_variant("- **Estimated effort:** Medium") == "medium"
    assert MODULE.determine_variant("- **Estimated effort:** High") == "high"


def test_determine_variant_reads_legacy_field_from_corrupted_json():
    description = (
        '{"snippet": "<label class="field">", '
        '"estimated_effort": "Medium", "description": "text"}'
    )

    assert MODULE.determine_variant(description) == "medium"


def test_model_map_uses_extracted_effort():
    assert MODULE.resolve_difficulty_config("low")["model"] == "gpt-5.6-luna"
    assert MODULE.resolve_difficulty_config("medium")["model"] == "gpt-5.6-terra"
    assert MODULE.resolve_difficulty_config("high")["model"] == "gpt-5.6-sol"
