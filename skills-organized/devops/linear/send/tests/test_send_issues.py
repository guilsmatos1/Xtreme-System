import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "send_issues.py"
SPEC = importlib.util.spec_from_file_location("send_issues", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_markdown_opportunities_preserves_body_and_routing_fields():
    text = """# Improvement opportunities

- **Generated:** 2026-07-29T12:00:00-03:00
- **Total:** 2

## imp-20260729-001 — First issue

- **Impact:** High
- **Category:** Security
- **Estimated effort:** High
- **Priority:** urgent
- **Tags:** security, api

### Description

Readable prose with `code`.

## imp-20260729-002 — Second issue

- **Impact:** Medium
- **Category:** Maintainability
- **Estimated effort:** Medium
- **Priority:** medium
- **Tags:** refactor
"""

    opportunities = MODULE.parse_markdown_opportunities(text)

    assert [item["short_title"] for item in opportunities] == [
        "First issue",
        "Second issue",
    ]
    assert opportunities[0]["estimated_effort"] == "High"
    assert opportunities[0]["additional_fields"] == {
        "priority": "urgent",
        "tags": ["security", "api"],
    }
    assert "Readable prose with `code`." in opportunities[0]["_markdown_body"]
    assert "Second issue" not in opportunities[0]["_markdown_body"]


def test_trailing_discarded_section_is_not_appended_to_last_opportunity():
    text = """# Improvement opportunities

- **Generated:** 2026-07-29T12:00:00-03:00
- **Total:** 1

## imp-20260729-001 — Only issue

- **Impact:** High
- **Category:** Security
- **Priority:** high
- **Tags:** security

### Description

Kept finding.

## Discarded candidates

### Rejected candidate

Reason it was not retained.
"""

    opportunities = MODULE.parse_markdown_opportunities(text)

    assert len(opportunities) == 1
    body = opportunities[0]["_markdown_body"]
    assert "Kept finding." in body
    assert "Discarded candidates" not in body
    assert "Rejected candidate" not in body


def test_legacy_json_opportunity_is_rendered_as_markdown():
    opportunity = {
        "id": "imp-20260729-001",
        "short_title": "Use Markdown",
        "impact": "Medium",
        "category": "Maintainability",
        "estimated_effort": "Medium",
        "description": 'A snippet contains class="field".',
        "additional_fields": {
            "priority": "medium",
            "risk_level": "low",
            "tags": ["linear", "markdown"],
        },
    }

    body = MODULE.opportunity_to_markdown(opportunity)

    assert body.startswith("## imp-20260729-001 — Use Markdown")
    assert "- **Estimated effort:** Medium" in body
    assert 'A snippet contains class="field".' in body
    assert '"estimated_effort":' not in body
