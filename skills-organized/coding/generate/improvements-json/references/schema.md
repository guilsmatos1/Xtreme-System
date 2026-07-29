# Improvements JSON contract

Write one JSON object with this shape:

```json
{
  "analysis_timestamp": "2026-07-29T12:00:00-03:00",
  "total_opportunities": 1,
  "opportunities": [
    {
      "id": "imp-20260729-001",
      "short_title": "Actionable title",
      "location": {
        "file": "path/to/file.py",
        "line_start": 120,
        "line_end": 131,
        "function": "function_name",
        "snippet": "8-12 lines copied from the current file"
      },
      "impact": "High",
      "category": "Security",
      "estimated_effort": "Medium",
      "potential_savings": "Concrete supported benefit",
      "description": "Specific explanation tied to the task and evidence",
      "why_it_matters": "Correctness, risk, maintenance, or operational consequence",
      "concrete_fix": "Smallest useful implementation change",
      "example": "Optional implementation example",
      "additional_fields": {
        "priority": "high",
        "risk_level": "medium",
        "tags": ["security", "api"],
        "files_affected": ["path/to/file.py"],
        "related_opportunities": []
      },
      "self_critique": {
        "confidence_score": 8.5,
        "strengths": ["Evidence that was verified"],
        "weaknesses": ["Unverified detail or assumption"],
        "uncertain": false,
        "suggested_improvements": ["Further check that would raise confidence"]
      }
    }
  ]
}
```

## Validation rules

- `analysis_timestamp` is a valid ISO-8601 timestamp with timezone.
- `total_opportunities` equals the length of `opportunities`.
- IDs are unique and match `^imp-[0-9]{8}-[0-9]{3}$`.
- `impact` is `High` or `Medium`.
- `estimated_effort` is `Low`, `Medium`, or `High`.
- `priority` and `risk_level` are `high`, `medium`, or `low`.
- `confidence_score` is a number from `0` through `10`.
- Verified locations contain positive line numbers, `line_start <= line_end`, and an actual 8-12
  line snippet from the named file.
- When no location can be verified, `location` is `null`, `uncertain` is `true`, and `weaknesses`
  explains what evidence is missing.
- `potential_savings` and `example` may be omitted when unsupported or unnecessary.
- `files_affected`, `tags`, and `related_opportunities` are arrays, even when empty.
- Every related ID exists in the same document and reciprocal relationships are consistent.
- The file is valid UTF-8 JSON and contains no Markdown fences or comments.
