"""Prompt templates for the new 10-step PPT generation pipeline."""
import json


def brief_decomposition_prompt(rfp_text: str, sheet_metadata_summary: str) -> str:
    rfp_section = f"\n\n## User Brief / RFP Document\n{rfp_text[:6000]}" if rfp_text.strip() else ""
    return f"""You are a senior business analyst decomposing a data presentation brief.

Given the data description and any user brief below, extract exactly 4 analytical fields
that will be reused throughout the presentation pipeline. Be concise and precise.

## Data Overview
{sheet_metadata_summary[:3000]}
{rfp_section}

Extract:
1. **domain_context** (~15-25 tokens): The business domain and dataset type.
   Example: "Retail FMCG sales performance across brands and SKUs in India"

2. **analytical_questions** (3-5 questions): The key business questions this data can answer.
   Each question should be specific, measurable, and answerable from the data.
   Example: "Which brands show the highest revenue growth quarter-over-quarter?"

3. **audience_and_tone**: A natural-language description of who will see this presentation
   and the appropriate communication style.
   Example: "Senior marketing executives; consultative tone with clear business impact framing"

4. **full_summary** (200-300 tokens): A comprehensive synthesis of the brief — what the data
   contains, what the presentation should achieve, and what success looks like.

Also extract:
- **presentation_title**: A compelling, specific title for the presentation deck
- **audience**: One of "executive" | "analyst" | "client"
- **tone**: One of "formal" | "consultative" | "technical"

Return only valid JSON matching the provided schema."""


def sheet_classification_prompt(sheet_name: str, metadata: dict, domain_context: str) -> str:
    columns_info = []
    for col in metadata.get('columns', []):
        dtype = metadata['inferred_dtypes'].get(col, 'unknown')
        unique = metadata['unique_counts'].get(col, '?')
        null = metadata['null_pct'].get(col, '?')
        columns_info.append(f"  - {col!r}: dtype={dtype}, unique={unique}, null%={null}")

    samples_str = json.dumps(metadata.get('sample_top', [])[:2], indent=2)

    return f"""You are a data analyst classifying columns in a business dataset.

Domain context: {domain_context}
Sheet: "{sheet_name}" ({metadata.get('row_count', '?')} rows)

Columns:
{chr(10).join(columns_info)}

Sample rows (top 2):
{samples_str}

Classify each column with one of these roles:
- "metric": Quantitative measure to aggregate/analyze (revenue, units, score, %)
- "dimension": Categorical grouping variable (brand, region, product, category)
- "date": Temporal column (date, month, quarter, year, period)
- "id": Row identifier — unique per row, no analytical value
- "foreign_key_candidate": ID-like but joins to another sheet (e.g. product_id, region_id)
- "text": Free-form text — descriptions, notes, names
- "irrelevant": Empty, redundant, or no analytical value

Also determine:
- **irrelevant_sheet**: true if the entire sheet has no analytical value (e.g. metadata, readme)
- **summary**: One-line description of what this sheet represents
- **confidence_notes**: Any columns you are uncertain about and why

Return only valid JSON matching the provided schema."""


def group_planning_prompt(classifications: dict, join_graph: dict,
                          analytical_questions: list[str]) -> str:
    class_summary = {}
    for sheet, cls in classifications.items():
        if cls.get('irrelevant_sheet'):
            continue
        roles = cls.get('column_roles', {})
        class_summary[sheet] = {
            'summary': cls.get('summary', ''),
            'metrics': [c for c, r in roles.items() if r == 'metric'],
            'dimensions': [c for c, r in roles.items() if r == 'dimension'],
            'dates': [c for c, r in roles.items() if r == 'date'],
            'fk_candidates': [c for c, r in roles.items() if r == 'foreign_key_candidate'],
        }

    fk_edges = join_graph.get('fk_edges', [])
    orphans = join_graph.get('orphan_sheets', [])

    questions_str = '\n'.join(f"  {i+1}. {q}" for i, q in enumerate(analytical_questions))

    return f"""You are a data analytics architect grouping related dataset sheets for analysis.

## Analytical Questions to Answer
{questions_str}

## Sheet Summaries & Column Roles
{json.dumps(class_summary, indent=2)}

## Detected Relationships (FK edges)
{json.dumps(fk_edges, indent=2)}

## Orphan Sheets (no detected relationships)
{orphans}

Create 2-3 analytical groups where each group:
- Contains 1-3 sheets that are analytically related (share dimensions, join via FK, or complement each other)
- Has a clear analytical framing tied to one or more of the questions above
- Can produce standalone business insights

For each group specify:
- **group_id**: "group_0", "group_1", etc.
- **sheets**: list of sheet names included
- **join_keys**: dict of {{sheet_a: col_a, sheet_b: col_b}} for each join in the group
- **analytical_framing**: What business question(s) this group answers (1-2 sentences)
- **orphan_handling**: For any orphan sheets, "include_standalone" or "exclude"

Rules:
- Each non-orphan sheet must appear in exactly one group
- Groups of 1 sheet are OK if the sheet is analytically rich
- Prefer grouping sheets that share a common dimension (brand, region, product)

Return only valid JSON — an array of group objects matching the schema."""


def insight_scan_prompt(group: dict, summary_stats: dict,
                        classifications: dict, analytical_questions: list[str]) -> str:
    group_sheets = group.get('sheets', [])
    sheet_summaries = {s: classifications.get(s, {}).get('summary', '') for s in group_sheets}
    questions_str = '\n'.join(f"  {i+1}. {q}" for i, q in enumerate(analytical_questions))

    return f"""You are a senior data analyst scanning a group of related datasets for analytical value.

## Group: {group.get('group_id')}
Sheets: {group_sheets}
Analytical framing: {group.get('analytical_framing', '')}

## Sheet Summaries
{json.dumps(sheet_summaries, indent=2)}

## Summary Statistics
{json.dumps(summary_stats, indent=2)[:4000]}

## Business Questions to Answer
{questions_str}

Based on the summary statistics:
1. Write 2-4 initial observations about notable patterns, outliers, or trends
2. Identify up to 8 high-value drill-down analyses to run, ranked by analytical importance

Each drill-down request must specify:
- **id**: unique string like "drill_g0_1"
- **drill_type**: one of "cross_tab" | "trend" | "comparison" | "correlation" | "gap_analysis"
- **sheets**: which sheets in this group to use
- **params**: type-specific parameters (see below)
- **rationale**: why this analysis is valuable

Drill-down param schemas by type:
- cross_tab: {{metric_col, group_by_col, agg_func: "sum"|"mean"|"count"}}
- trend: {{metric_col, date_col, freq: "M"|"Q"|"Y"}}
- comparison: {{metric_col, dimension_col, top_n: int, agg_func: "sum"|"mean"}}
- correlation: {{metric_col_a, metric_col_b, sheet_a, sheet_b}}
- gap_analysis: {{key_col_a, sheet_a, key_col_b, sheet_b}}

Return only valid JSON matching the provided schema."""


def insight_extraction_prompt_v2(group: dict, summary_stats: dict,
                                  drill_results: dict, full_summary: str) -> str:
    return f"""You are a senior market research analyst extracting business insights from data analysis results.

## Brief Context
{full_summary[:1000]}

## Group: {group.get('group_id')}
Analytical framing: {group.get('analytical_framing', '')}
Sheets: {group.get('sheets', [])}

## Summary Statistics
{json.dumps(summary_stats, indent=2)[:2000]}

## Drill-Down Analysis Results
{json.dumps(drill_results, indent=2)[:4000]}

Extract 3-6 ranked business insights from this group. For each insight:

- **insight_id**: unique string like "ins_g0_1"
- **group_id**: "{group.get('group_id')}"
- **title**: Punchy 8-12 word headline (specific, not generic — include numbers if possible)
- **finding**: The key business insight in 2-3 sentences with specific data points
- **magnitude**: "high" | "medium" | "low" (business impact)
- **source_sheets**: which sheets in the group support this insight
- **supporting_data**: key numbers/values that back this insight (dict)
- **visualization_type**: best chart type — "bar_chart"|"line_chart"|"scatter"|"pie_chart"|"heatmap"|"grouped_bar"|"waterfall"
- **narrative_hook**: one sentence connecting this insight to the analytical questions
- **priority**: integer (1=highest priority for slide planning)

Rules:
- Include only genuine insights, not obvious observations
- Prioritize insights that directly answer the analytical questions
- Each insight must be supported by specific data from the drill-down results
- Avoid overlapping insights

Return only valid JSON — an array of insight objects matching the schema."""


def slide_planning_prompt_v2(all_insights: dict, full_summary: str,
                              audience_and_tone: str) -> str:
    insights_flat = []
    for group_id, insights in all_insights.items():
        for ins in insights:
            insights_flat.append(ins)
    insights_flat.sort(key=lambda x: x.get('priority', 99))

    return f"""You are a consulting presentation architect designing a data-driven slide deck.

## Brief & Context
{full_summary[:1500]}

## Audience & Tone
{audience_and_tone}

## Available Insights (ranked by priority)
{json.dumps(insights_flat, indent=2)[:5000]}

Design a complete slide deck following BLUF (Bottom Line Up Front) structure:
1. Title slide
2. Executive summary (key findings upfront)
3. Evidence slides (3-8 slides presenting insights with data)
4. Recommendations / so-what slide
5. Appendix (optional — 0-2 slides with supporting detail)

For each slide, specify:
- **slide_index**: 0-based integer
- **slide_type**: "title"|"overview"|"chart"|"insight"|"comparison"|"executive_summary"|"recommendation"|"data_table"
- **title**: The "so what" message as a complete sentence (not a topic label)
- **subtitle**: Supporting context (optional)
- **key_message**: The single most important takeaway from this slide (1 sentence)
- **content_type**: "chart"|"bullets"|"narrative"|"table"
- **visualization_spec**: (required for chart slides, null for others)
  {{
    "chart_type": "bar_chart"|"line_chart"|"scatter"|"pie_chart"|"heatmap"|"grouped_bar"|"waterfall",
    "source_group": "group_id",
    "source_sheets": ["sheet_name"],
    "x_col": "column_name",
    "y_cols": ["column_name"],
    "color_col": null,
    "filter_expr": null,
    "sort_by": null,
    "top_n": null,
    "join_on": null,
    "agg_func": "sum"|"mean"|"count"|"max"|"min"
  }}
- **data_points**: list of 2-4 specific numbers/facts to highlight (for bullet/narrative slides)
- **bullet_points**: list of 3-6 bullets (for bullet slides)
- **speaker_notes**: 2-3 sentences for the presenter
- **insight_refs**: list of insight_id strings that back this slide

Rules:
- Total slides: 6-12 (not counting appendix)
- Every chart slide must have a valid visualization_spec referencing actual columns from the insights
- Column names in visualization_spec must exactly match column names from the source sheets
- First slide must be type "title"
- Include exactly one "executive_summary" slide
- The narrative_arc field describes the overall story arc in 2-3 sentences

Return only valid JSON with keys: narrative_arc, executive_summary_bullets, slides, appendix_slides."""
