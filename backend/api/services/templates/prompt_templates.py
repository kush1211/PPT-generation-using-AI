"""All Gemini prompt strings for the PPT generation pipeline."""


def objective_inference_prompt(rfp_text: str, condensed_repr: str) -> str:
    return f"""You are a senior business analyst. Extract structured presentation objectives from the RFP/requirement document and dataset provided below.

DOCUMENT CONTENT:
{rfp_text[:6000]}

DATASET SUMMARY:
{condensed_repr}

Extract the presentation objectives. Be specific and actionable. For audience use one of: executive, analyst, client. For tone use one of: formal, consultative, technical."""


def insight_extraction_prompt(condensed_repr: str, objectives_json: str, stats_json: str) -> str:
    return f"""You are a senior market research analyst. Identify the most important, non-obvious insights from this dataset given the business objectives below.

Focus on: outliers, trends, comparisons, anomalies, competitive dynamics. Prioritize insights that are actionable and directly serve the stated objectives. Use exact numbers from the data.

OBJECTIVES:
{objectives_json}

DATASET SUMMARY:
{condensed_repr}

DETAILED STATISTICS:
{stats_json}

Identify 6-8 insights ordered by business impact. For chart_hint use one of: bar_chart, line_chart, scatter, pie_chart, heatmap, grouped_bar, waterfall. For magnitude use: high, medium, or low."""


def slide_planning_prompt(insights_json: str, objectives_json: str) -> str:
    return f"""You are a consulting presentation architect. Design an ordered PowerPoint slide deck that tells a coherent analytical story following the BLUF (Bottom Line Up Front) structure: start with the key finding, support with evidence, end with recommendations.

Every slide must have a single clear "so what" message as its title — not a topic label.

OBJECTIVES:
{objectives_json}

INSIGHTS (ordered by priority):
{insights_json}

Design 8-12 slides. The first slide must be type "title". Include at least one "executive_summary" slide near the end. For slide_type use one of: title, overview, chart, insight, comparison, executive_summary, recommendation, data_table."""


def narrative_writing_prompt(slide_title: str, insight_finding: str, data_points: str,
                              chart_type: str, narrative_hint: str,
                              audience: str, tone: str) -> tuple[str, str]:
    system = f"""You are a domain-expert market research analyst writing slide narratives for a {audience} audience in a {tone} tone.
Write 3-5 sentences. Start with the key finding. Follow with 1-2 sentences of supporting evidence using exact numbers. End with a forward-looking implication or recommendation.
Do NOT use generic phrases like "as we can see from the chart" or "the data shows". Be specific: use exact numbers, percentages, entity names from the data."""

    user = f"""SLIDE TITLE: {slide_title}
KEY FINDING: {insight_finding}
SUPPORTING DATA POINTS: {data_points}
CHART TYPE SHOWN: {chart_type}
NARRATIVE FOCUS: {narrative_hint}

Write the analyst narrative for this slide."""
    return system, user


def intent_classification_prompt(user_message: str, slide_manifest: str, chat_history: str) -> str:
    return f"""You are a chat intent classifier for a PowerPoint presentation assistant.

PRESENTATION SLIDES:
{slide_manifest}

RECENT CHAT HISTORY:
{chat_history}

USER MESSAGE: "{user_message}"

Classify this intent. For intent_type use one of: explain, add_chart, rewrite, filter, compare, question, regenerate.
Extract target_slide_index (0-based, or -1 if not applicable), subject (entity being discussed), and relevant parameters."""


def chat_answer_prompt(user_message: str, slide_content: str,
                       condensed_repr: str, objectives_summary: str) -> tuple[str, str]:
    system = """You are a senior market research analyst answering questions about a presentation you built.
Answer concisely with specific data references. Use exact numbers and entity names. Answer in 2-4 sentences."""

    user = f"""QUESTION: {user_message}

RELEVANT SLIDE CONTENT:
{slide_content}

DATA CONTEXT:
{condensed_repr}

PRESENTATION OBJECTIVES:
{objectives_summary}"""
    return system, user


def narrative_rewrite_prompt(original_narrative: str, current_audience: str,
                              new_audience: str, data_context: str) -> tuple[str, str]:
    system = f"""You are rewriting a slide narrative for a different audience.
Maintain ALL factual data points and numbers. Adjust vocabulary complexity, level of detail, emphasis on business impact vs. technical analysis, and call-to-action strength to suit the new audience."""

    user = f"""ORIGINAL NARRATIVE (written for {current_audience}):
{original_narrative}

NEW AUDIENCE: {new_audience}

DATA CONTEXT:
{data_context}

Rewrite this narrative for the {new_audience} audience in 3-5 sentences."""
    return system, user
