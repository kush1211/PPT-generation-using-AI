"""Pipeline Orchestrator: runs Steps 2-8 as a LangGraph StateGraph.

Each pipeline step is a LangGraph node. The graph flows linearly:
  load_sheets → classify_sheets → discover_relationships → plan_groups
  → profile_groups → scan_drills → targeted_profiling → extract_insights
  → plan_slides → build_pptx

LangSmith traces every node automatically when LANGCHAIN_TRACING_V2=true.
"""
import logging
import time
from typing import Any, TypedDict

from django.conf import settings
from langgraph.graph import StateGraph, END

from ..data_ingestion.multi_sheet_loader import load_all_sheets
from ..data_ingestion.relationship_discovery import discover_relationships
from ..data_ingestion.summary_profiler import profile_groups
from ..data_ingestion.targeted_profiler import run_drill_downs
from ..analysis.sheet_classifier import classify_sheets
from ..analysis.group_planner import plan_groups
from ..analysis.insight_scanner import scan_groups_for_drills, extract_insights_from_groups
from .slide_planner_v2 import plan_slides_v2
from .chart_builder import build_chart
from .narrative_writer import write_narrative
from .ppt_builder import build_presentation

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    project: Any           # Django Project model instance
    file_path: str
    sheet_dfs: dict        # {sheet_name: DataFrame}
    classifications: dict
    join_graph: dict
    groups: list
    summary_stats: dict
    scan_results: dict
    drill_results: dict
    all_insights: dict
    slide_plan: dict
    result: dict


# ── Node functions ─────────────────────────────────────────────────────────────

def node_load_sheets(state: PipelineState) -> dict:
    _log("load_sheets", "Loading sheet DataFrames")
    sheet_dfs = load_all_sheets(state["file_path"])
    logger.info("Loaded %d sheets: %s", len(sheet_dfs), list(sheet_dfs.keys()))
    return {"sheet_dfs": sheet_dfs}


def node_classify_sheets(state: PipelineState) -> dict:
    _log("classify_sheets", "Classifying sheets (Step 2)")
    t = time.time()
    project = state["project"]
    classifications = classify_sheets(
        project.data_file.sheet_metadata,
        project.brief.domain_context,
    )
    project.data_file.sheet_classifications = classifications
    project.data_file.save(update_fields=["sheet_classifications"])
    logger.info("Step 2 done (%.1fs): %d sheets classified", time.time() - t, len(classifications))
    return {"classifications": classifications}


def node_discover_relationships(state: PipelineState) -> dict:
    _log("discover_relationships", "Discovering relationships (Step 3)")
    t = time.time()
    join_graph = discover_relationships(state["sheet_dfs"], state["classifications"])
    project = state["project"]
    project.data_file.relationship_graph = join_graph
    project.data_file.save(update_fields=["relationship_graph"])
    logger.info(
        "Step 3 done (%.1fs): %d FK edges, %d orphans",
        time.time() - t,
        len(join_graph.get("fk_edges", [])),
        len(join_graph.get("orphan_sheets", [])),
    )
    return {"join_graph": join_graph}


def node_plan_groups(state: PipelineState) -> dict:
    from api.models import SheetGroup
    _log("plan_groups", "Planning sheet groups (Step 4)")
    t = time.time()
    project = state["project"]
    groups = plan_groups(
        state["classifications"],
        state["join_graph"],
        project.brief.analytical_questions,
    )
    SheetGroup.objects.filter(project=project).delete()
    for g in groups:
        SheetGroup.objects.create(
            project=project,
            group_id=g["group_id"],
            sheet_names=g.get("sheets", []),
            join_keys=g.get("join_keys", {}),
            analytical_framing=g.get("analytical_framing", ""),
        )
    logger.info("Step 4 done (%.1fs): %d groups", time.time() - t, len(groups))
    return {"groups": groups}


def node_profile_groups(state: PipelineState) -> dict:
    _log("profile_groups", "Profiling groups (Step 5)")
    t = time.time()
    summary_stats = profile_groups(state["sheet_dfs"], state["groups"], state["classifications"])
    project = state["project"]
    project.data_file.summary_stats = summary_stats
    project.data_file.save(update_fields=["summary_stats"])
    logger.info("Step 5 done (%.1fs)", time.time() - t)
    return {"summary_stats": summary_stats}


def node_scan_drills(state: PipelineState) -> dict:
    from api.models import SheetGroup
    _log("scan_drills", "Scanning for drill-down opportunities (Step 6a)")
    t = time.time()
    project = state["project"]
    scan_results = scan_groups_for_drills(
        state["groups"],
        state["summary_stats"],
        state["classifications"],
        project.brief.analytical_questions,
    )
    for sg in SheetGroup.objects.filter(project=project):
        sg.insight_scan_raw = scan_results.get(sg.group_id, {})
        sg.save(update_fields=["insight_scan_raw"])
    logger.info("Step 6a done (%.1fs)", time.time() - t)
    return {"scan_results": scan_results}


def node_targeted_profiling(state: PipelineState) -> dict:
    from api.models import SheetGroup
    _log("targeted_profiling", "Running targeted drill-downs (Step 6b)")
    t = time.time()
    project = state["project"]
    drill_results: dict = {}
    for sg in SheetGroup.objects.filter(project=project):
        drill_requests = sg.insight_scan_raw.get("drill_requests", [])
        dr = run_drill_downs(state["sheet_dfs"], drill_requests, sg.sheet_names)
        sg.drill_down_results = dr
        sg.save(update_fields=["drill_down_results"])
        drill_results[sg.group_id] = dr
    logger.info("Step 6b done (%.1fs): %d groups drilled", time.time() - t, len(drill_results))
    return {"drill_results": drill_results}


def node_extract_insights(state: PipelineState) -> dict:
    from api.models import SheetGroup, Insight
    _log("extract_insights", "Extracting insights (Step 6c)")
    t = time.time()
    project = state["project"]
    all_insights = extract_insights_from_groups(
        state["groups"],
        state["summary_stats"],
        state["drill_results"],
        project.brief.full_summary,
    )
    Insight.objects.filter(project=project).delete()
    for sg in SheetGroup.objects.filter(project=project):
        group_insights = all_insights.get(sg.group_id, [])
        sg.insights_extracted = group_insights
        sg.save(update_fields=["insights_extracted"])
        for ins in group_insights:
            Insight.objects.create(
                project=project,
                insight_id=ins.get("insight_id", f"ins_{sg.group_id}_{len(group_insights)}"),
                title=ins.get("title", ""),
                finding=ins.get("finding", ""),
                magnitude=ins.get("magnitude", "medium"),
                data_slice=ins.get("supporting_data", {}),
                chart_hint=ins.get("visualization_type", "bar_chart"),
                priority=ins.get("priority", 99),
            )
    total_insights = sum(len(v) for v in all_insights.values())
    logger.info("Step 6c done (%.1fs): %d total insights", time.time() - t, total_insights)
    return {"all_insights": all_insights}


def node_plan_slides(state: PipelineState) -> dict:
    _log("plan_slides", "Planning slides (Step 7)")
    t = time.time()
    project = state["project"]
    slide_plan = plan_slides_v2(
        state["all_insights"],
        project.brief.full_summary,
        project.brief.audience_and_tone,
    )
    logger.info(
        "Step 7 done (%.1fs): %d slides planned",
        time.time() - t,
        len(slide_plan.get("slides", [])),
    )
    return {"slide_plan": slide_plan}


def node_build_pptx(state: PipelineState) -> dict:
    from api.models import Slide
    _log("build_pptx", "Building presentation (Step 8)")
    t = time.time()

    project = state["project"]
    all_insights = state["all_insights"]
    sheet_dfs = state["sheet_dfs"]
    groups = state["groups"]
    slide_plan = state["slide_plan"]

    objectives = project.objectives
    audience = getattr(objectives, "audience", "executive")
    tone = getattr(objectives, "tone", "consultative")

    insight_map = {
        ins.get("insight_id", ""): ins
        for group_insights in all_insights.values()
        for ins in group_insights
    }

    Slide.objects.filter(project=project).delete()
    slides_for_ppt = []
    _NO_CHART_TYPES = {"title", "overview", "executive_summary", "recommendation"}

    for spec in slide_plan.get("slides", []):
        slide_type = spec.get("slide_type", "chart")
        slide_title = spec.get("title", "")
        key_message = spec.get("key_message", "")
        viz_spec = spec.get("visualization_spec")

        chart_path = ""
        chart_json_str = ""
        chart_config = {}

        if slide_type not in _NO_CHART_TYPES:
            # Primary: use visualization_spec from slide plan
            if viz_spec and isinstance(viz_spec, dict) and viz_spec:
                print(f"[CHART] Slide {slide_title!r}: viz_spec keys={list(viz_spec.keys())}", flush=True)
                try:
                    df = _resolve_dataframe(viz_spec, sheet_dfs, groups)
                    chart_config = _viz_spec_to_chart_config(viz_spec, slide_title)
                    chart_path, chart_json_str = build_chart(chart_config, df)
                    if chart_path:
                        print(f"[CHART] Built OK → {chart_path}", flush=True)
                    else:
                        print(f"[CHART] build_chart returned empty path — falling back", flush=True)
                except Exception as e:
                    print(f"[CHART] Primary build failed: {e}", flush=True)
                    logger.warning("Chart build failed for slide %r: %s", slide_title, e)
            else:
                print(f"[CHART] Slide {slide_title!r}: viz_spec empty — using fallback", flush=True)

            # Fallback: build from insight supporting_data
            if not chart_path:
                try:
                    chart_path, chart_json_str, chart_config = _build_fallback_chart(
                        spec, insight_map, sheet_dfs, groups, slide_title
                    )
                    if chart_path:
                        print(f"[CHART] Fallback built OK → {chart_path}", flush=True)
                    else:
                        print(f"[CHART] Fallback also empty — slide will have no chart", flush=True)
                except Exception as e2:
                    print(f"[CHART] Fallback chart failed: {e2}", flush=True)
                    logger.warning("Fallback chart failed for slide %r: %s", slide_title, e2)

        narrative = ""
        if slide_type != "title":
            try:
                insight_for_narr = {
                    "finding": key_message,
                    "data_slice": {"data_points": spec.get("data_points", [])},
                }
                narrative = write_narrative(
                    slide_title=slide_title,
                    insight=insight_for_narr,
                    chart_type=viz_spec.get("chart_type", "bar_chart") if viz_spec else "bar_chart",
                    narrative_hint=spec.get("speaker_notes", ""),
                    audience=audience,
                    tone=tone,
                )
            except Exception as e:
                logger.warning("Narrative failed for slide %r: %s", slide_title, e)
                narrative = key_message

        slide_obj = Slide.objects.create(
            project=project,
            slide_index=spec.get("slide_index", 0),
            slide_type=slide_type,
            title=slide_title,
            subtitle=spec.get("subtitle", ""),
            narrative=narrative,
            bullet_points=spec.get("bullet_points", []),
            speaker_notes=spec.get("speaker_notes", ""),
            insight_ids=spec.get("insight_refs", []),
            chart_config=chart_config,
        )
        if chart_path:
            slide_obj.chart_png = chart_path
            slide_obj.chart_json = chart_json_str
            slide_obj.save()

        slides_for_ppt.append({
            "slide_index": spec.get("slide_index", 0),
            "slide_type": slide_type,
            "title": slide_title,
            "subtitle": spec.get("subtitle", ""),
            "narrative": narrative,
            "chart_png": chart_path,
            "bullet_points": spec.get("bullet_points", []),
            "speaker_notes": spec.get("speaker_notes", ""),
            "insight_ids": spec.get("insight_refs", []),
            "chart_config": chart_config,
        })

    pptx_rel_path = build_presentation(slides_for_ppt)
    project.pptx_file = pptx_rel_path
    project.status = "ready"
    project.save()

    logger.info("Step 8 done (%.1fs): PPT assembled", time.time() - t)
    return {"result": {"slide_count": len(slides_for_ppt), "pptx_path": pptx_rel_path}}


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_graph() -> Any:
    graph = StateGraph(PipelineState)

    graph.add_node("load_sheets", node_load_sheets)
    graph.add_node("classify_sheets", node_classify_sheets)
    graph.add_node("discover_relationships", node_discover_relationships)
    graph.add_node("plan_groups", node_plan_groups)
    graph.add_node("profile_groups", node_profile_groups)
    graph.add_node("scan_drills", node_scan_drills)
    graph.add_node("targeted_profiling", node_targeted_profiling)
    graph.add_node("extract_insights", node_extract_insights)
    graph.add_node("plan_slides", node_plan_slides)
    graph.add_node("build_pptx", node_build_pptx)

    graph.set_entry_point("load_sheets")
    graph.add_edge("load_sheets", "classify_sheets")
    graph.add_edge("classify_sheets", "discover_relationships")
    graph.add_edge("discover_relationships", "plan_groups")
    graph.add_edge("plan_groups", "profile_groups")
    graph.add_edge("profile_groups", "scan_drills")
    graph.add_edge("scan_drills", "targeted_profiling")
    graph.add_edge("targeted_profiling", "extract_insights")
    graph.add_edge("extract_insights", "plan_slides")
    graph.add_edge("plan_slides", "build_pptx")
    graph.add_edge("build_pptx", END)

    return graph.compile()


_pipeline = _build_graph()


# ── Public entry point ─────────────────────────────────────────────────────────

def run_generation_pipeline(project) -> dict:
    """Run the full generation pipeline via LangGraph.
    Called by GenerateView.post().
    """
    t0 = time.time()
    file_path = str(settings.MEDIA_ROOT / project.data_file.file.name)

    initial_state: PipelineState = {
        "project": project,
        "file_path": file_path,
        "sheet_dfs": {},
        "classifications": {},
        "join_graph": {},
        "groups": [],
        "summary_stats": {},
        "scan_results": {},
        "drill_results": {},
        "all_insights": {},
        "slide_plan": {},
        "result": {},
    }

    final_state = _pipeline.invoke(initial_state)
    logger.info("Total pipeline time: %.1fs", time.time() - t0)
    return final_state["result"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _log(node: str, description: str) -> None:
    print(f"\n[PIPELINE] [{node.upper()}] {description}...", flush=True)


def _viz_spec_to_chart_config(viz_spec: dict, title: str = "") -> dict:
    return {
        "chart_type": viz_spec.get("chart_type", "bar_chart"),
        "x_col": viz_spec.get("x_col", ""),
        "y_cols": viz_spec.get("y_cols", []),
        "color_col": viz_spec.get("color_col"),
        "filter_expr": viz_spec.get("filter_expr"),
        "title": title,
        "sort_by": viz_spec.get("sort_by"),
        "top_n": viz_spec.get("top_n"),
    }


def _resolve_dataframe(viz_spec: dict, sheet_dfs: dict, groups: list):
    import pandas as pd

    source_sheets = viz_spec.get("source_sheets") or []
    join_on = viz_spec.get("join_on")
    agg_func = viz_spec.get("agg_func")

    source_group_id = viz_spec.get("source_group", "")
    group = next((g for g in groups if g["group_id"] == source_group_id), None)
    fallback_sheets = group["sheets"] if group else list(sheet_dfs.keys())

    sheets_to_use = [s for s in source_sheets if s in sheet_dfs]
    if not sheets_to_use:
        sheets_to_use = [s for s in fallback_sheets if s in sheet_dfs]
    if not sheets_to_use:
        sheets_to_use = list(sheet_dfs.keys())[:1]

    if len(sheets_to_use) == 1 or not join_on:
        df = sheet_dfs[sheets_to_use[0]].copy()
    else:
        sheet_a, sheet_b = sheets_to_use[0], sheets_to_use[1]
        col_a, col_b = join_on.get(sheet_a), join_on.get(sheet_b)
        df_a, df_b = sheet_dfs[sheet_a], sheet_dfs[sheet_b]
        if col_a and col_b and col_a in df_a.columns and col_b in df_b.columns:
            df = pd.merge(df_a, df_b, left_on=col_a, right_on=col_b, how="inner")
        else:
            df = df_a.copy()

    if agg_func:
        x_col = viz_spec.get("x_col", "")
        y_cols = viz_spec.get("y_cols", [])
        valid_y = [c for c in y_cols if c in df.columns]
        if x_col in df.columns and valid_y:
            df = df.groupby(x_col)[valid_y].agg(agg_func).reset_index()

    return df


def _build_fallback_chart(spec: dict, insight_map: dict, sheet_dfs: dict,
                           groups: list, slide_title: str) -> tuple:
    import pandas as pd

    insight_refs = spec.get("insight_refs", [])
    insight = next((insight_map[r] for r in insight_refs if r in insight_map), None)

    if insight:
        supporting_data = insight.get("supporting_data", {})
        chart_hint = insight.get("visualization_type", "bar_chart")
        source_sheets = insight.get("source_sheets", [])

        numeric_pairs = [(k, v) for k, v in supporting_data.items()
                         if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(numeric_pairs) >= 2:
            df_fb = pd.DataFrame(numeric_pairs, columns=["Metric", "Value"])
            df_fb = df_fb.sort_values("Value", ascending=False)
            cfg = {
                "chart_type": chart_hint if chart_hint in (
                    "bar_chart", "pie_chart", "line_chart", "grouped_bar") else "bar_chart",
                "x_col": "Metric",
                "y_cols": ["Value"],
                "color_col": None,
                "filter_expr": None,
                "title": slide_title,
                "sort_by": "Value",
                "top_n": 10,
            }
            path, json_str = build_chart(cfg, df_fb)
            return path, json_str, cfg

        for sheet_name in source_sheets:
            if sheet_name in sheet_dfs:
                path, json_str, cfg = _chart_from_sheet(sheet_dfs[sheet_name], chart_hint, slide_title)
                if path:
                    return path, json_str, cfg

    if sheet_dfs:
        primary = max(sheet_dfs.values(), key=len)
        path, json_str, cfg = _chart_from_sheet(primary, "bar_chart", slide_title)
        return path, json_str, cfg

    return "", "", {}


def _chart_from_sheet(df, chart_type: str, title: str) -> tuple:
    dim_cols = df.select_dtypes(exclude="number").columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()

    if not num_cols:
        return "", "", {}

    x_col = dim_cols[0] if dim_cols else df.columns[0]
    y_col = num_cols[0]

    try:
        grouped = df.groupby(x_col)[y_col].sum().reset_index()
        grouped = grouped.sort_values(y_col, ascending=False).head(12)
    except Exception:
        grouped = df[[x_col, y_col]].dropna().head(12)

    cfg = {
        "chart_type": chart_type if chart_type in (
            "bar_chart", "pie_chart", "line_chart", "grouped_bar", "scatter") else "bar_chart",
        "x_col": x_col,
        "y_cols": [y_col],
        "color_col": None,
        "filter_expr": None,
        "title": title,
        "sort_by": y_col,
        "top_n": None,
    }
    path, json_str = build_chart(cfg, grouped)
    return path, json_str, cfg
