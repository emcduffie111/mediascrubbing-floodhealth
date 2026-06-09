"""Report generation helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_summary_report(
    case_study_name: str,
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    unique_mappings: list[dict[str, str]],
    svo_df: pd.DataFrame,
) -> str:
    summary = f"""# Semantic Bridge Analysis Report

## {case_study_name}

**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

---

## Analysis Summary

- **Documents Analyzed:** {len(transcripts)}
- **Topics Identified:** {n_topics}
- **Scientific Domains:** {len(set(m['primary_domain'] for m in topic_mappings))}
- **Decision Components:** {sum(len(v) for v in decision_components.values())}
- **Scientific Variables:** {len(set(m['scientific_variable'] for m in unique_mappings))}

---

## Key Findings

### Topics Discovered

"""
    for mapping in topic_mappings:
        summary += f"""**{mapping['topic']}**
- Keywords: {mapping['keywords']}
- Primary Domain: {mapping['primary_domain']}
"""
        if mapping["secondary_domain"]:
            summary += f"- Secondary Domain: {mapping['secondary_domain']}\n"
        summary += "\n"

    summary += """---

### Scientific Domains Engaged

"""
    for domain, count in svo_df.groupby("domain").size().sort_values(ascending=False).items():
        summary += f"- **{domain}:** {count} variables\n"

    summary += """
---

### Decision Components Extracted

"""
    for comp_type, items in decision_components.items():
        if items:
            summary += f"\n**{comp_type.title()}** ({len(items)}): "
            summary += ", ".join([item["text"] for item in items[:3]])
            if len(items) > 3:
                summary += f" ... (+{len(items) - 3} more)"
            summary += "\n"

    summary += """
---

## Outputs Generated

The following files have been created in the `outputs/` directory:

1. **Topic Mappings:** Links discovered topics to scientific domains
2. **Decision Components:** Extracted goals, objectives, variables, constraints, and indicators
3. **SVO Mappings:** Semantic links between natural language and scientific variables
4. **Network Visualization:** Interactive visualization of the science backbone
5. **Analysis Report:** This comprehensive summary document

---

## Next Steps

1. **Validate results** with domain experts and stakeholders
2. **Refine vocabularies** (`science_backbone` and `svo_vocabulary`) based on feedback
3. **Integrate** with computational models and decision support systems
4. **Iterate** the analysis with additional documents or refined parameters
5. **Deploy** as part of a larger decision pathways workflow
"""
    return summary


def write_report(output_dir: Path, case_study_name: str, summary: str) -> Path:
    report_path = output_dir / f"{case_study_name}_report.md"
    report_path.write_text(summary)
    return report_path

