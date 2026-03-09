import os
import uuid
import random
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from django.conf import settings

# Vibrant multi-palette system — each chart gets a randomly selected palette
# so slides look visually distinct while charts remain consistently bold
_PALETTES = [
    ['#E63946', '#F4A261', '#2A9D8F', '#457B9D', '#8338EC', '#06D6A0', '#FFB703'],  # bold mixed
    ['#06D6A0', '#FFB703', '#FB8500', '#3A86FF', '#FF006E', '#8338EC', '#2A9D8F'],  # vivid neon
    ['#264653', '#2A9D8F', '#E9C46A', '#F4A261', '#E76F51', '#457B9D', '#7209B7'],  # earthy bright
    ['#7209B7', '#3A0CA3', '#4361EE', '#4CC9F0', '#F72585', '#06D6A0', '#FFB703'],  # electric
    ['#FF595E', '#FFCA3A', '#6A4C93', '#1982C4', '#8AC926', '#FF595E', '#6A4C93'],  # pop
]

PRIMARY = '#1F3864'
ACCENT = '#C9A84C'
# Default fallback palette
PALETTE = _PALETTES[0]


def _get_palette() -> list:
    return random.choice(_PALETTES)


def build_chart(chart_config: dict, df: pd.DataFrame, output_dir: str = None) -> tuple:
    """Build a Plotly chart and export as PNG. Returns (rel_path, json_str)."""
    if output_dir is None:
        output_dir = str(settings.MEDIA_ROOT / 'charts')
    os.makedirs(output_dir, exist_ok=True)

    filter_expr = chart_config.get('filter_expr')
    if filter_expr:
        try:
            df = df.query(filter_expr)
        except Exception:
            pass

    top_n = chart_config.get('top_n')
    x_col = chart_config.get('x_col', '')
    y_cols = chart_config.get('y_cols', [])
    color_col = chart_config.get('color_col')
    title = chart_config.get('title', '')
    sort_by = chart_config.get('sort_by')
    chart_type = chart_config.get('chart_type', 'bar_chart')

    # Case-insensitive column matching
    def _match_col(name, columns):
        if not name:
            return None
        if name in columns:
            return name
        name_norm = name.strip().lower().replace(' ', '_').replace('-', '_')
        for c in columns:
            if c.strip().lower().replace(' ', '_').replace('-', '_') == name_norm:
                return c
        return None

    x_col = _match_col(x_col, df.columns) or (df.columns[0] if len(df.columns) > 0 else '')
    y_cols = [_match_col(c, df.columns) for c in y_cols]
    y_cols = [c for c in y_cols if c is not None]
    if not y_cols:
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        y_cols = numeric_cols[:1] if numeric_cols else []
    if not y_cols:
        return '', ''

    y_col = y_cols[0]

    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)
    if top_n:
        df = df.head(int(top_n))

    palette = _get_palette()
    fig = _build_figure(chart_type, df, x_col, y_cols, y_col, color_col, title, chart_config, palette)

    fig.update_layout(
        plot_bgcolor='#FAFAFA',
        paper_bgcolor='white',
        font=dict(family='Helvetica Neue, Arial, sans-serif', size=13, color='#2F2F2F'),
        title=dict(
            text=f'<b>{title}</b>' if title else '',
            font=dict(size=17, color='#1F3864'),
            x=0.04,
            xanchor='left',
        ),
        margin=dict(l=60, r=40, t=70, b=60),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            font=dict(size=12),
        ),
        xaxis=dict(showgrid=False, linecolor='#DDDDDD', tickfont=dict(size=12)),
        yaxis=dict(gridcolor='#EFEFEF', linecolor='#DDDDDD', tickfont=dict(size=12)),
    )

    filename = f"chart_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(output_dir, filename)
    fig.write_image(filepath, width=960, height=520, scale=1.5)
    return f"charts/{filename}", fig.to_json()


def _build_figure(chart_type, df, x_col, y_cols, y_col, color_col, title, config, palette):
    if chart_type == 'bar_chart':
        fig = px.bar(
            df, x=x_col, y=y_col, color=color_col,
            color_discrete_sequence=palette,
            text_auto='.2s',
        )
        fig.update_traces(
            textposition='outside',
            marker_line_width=0,
            opacity=0.92,
        )

    elif chart_type == 'line_chart':
        kw = dict(color=color_col) if color_col and color_col in df.columns else {}
        fig = px.line(
            df, x=x_col, y=y_col,
            color_discrete_sequence=palette,
            markers=True,
            **kw,
        )
        fig.update_traces(line_width=3, marker_size=8)

    elif chart_type == 'scatter':
        fig = px.scatter(
            df, x=x_col, y=y_col, color=color_col,
            color_discrete_sequence=palette,
            size_max=18,
        )
        fig.update_traces(marker_opacity=0.85, marker_line_width=1, marker_line_color='white')

    elif chart_type == 'pie_chart':
        fig = px.pie(
            df, names=x_col, values=y_col,
            color_discrete_sequence=palette,
            hole=0.42,
        )
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            pull=[0.03] * min(len(df), 20),
            marker_line_width=2,
            marker_line_color='white',
        )

    elif chart_type == 'heatmap':
        try:
            pivot_col = color_col or (y_cols[1] if len(y_cols) > 1 else x_col)
            pivot = df.pivot_table(index=x_col, columns=pivot_col, values=y_col)
            fig = px.imshow(pivot, color_continuous_scale='Turbo', text_auto='.1f')
        except Exception:
            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=palette)

    elif chart_type == 'grouped_bar':
        if len(y_cols) > 1:
            fig = px.bar(df, x=x_col, y=y_cols, barmode='group',
                         color_discrete_sequence=palette)
        elif color_col and color_col in df.columns:
            fig = px.bar(df, x=x_col, y=y_col, color=color_col, barmode='group',
                         color_discrete_sequence=palette)
        else:
            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=palette)
        fig.update_traces(marker_line_width=0, opacity=0.92)

    elif chart_type == 'waterfall':
        if pd.api.types.is_numeric_dtype(df[y_col]):
            bar_colors = [palette[0] if v >= 0 else '#C00000' for v in df[y_col]]
            fig = go.Figure(go.Bar(
                x=df[x_col].astype(str),
                y=df[y_col],
                marker_color=bar_colors,
                text=df[y_col].round(1),
                textposition='outside',
            ))
        else:
            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=palette)

    elif chart_type == 'area_chart':
        kw = dict(color=color_col) if color_col and color_col in df.columns else {}
        fig = px.area(df, x=x_col, y=y_col, color_discrete_sequence=palette, **kw)
        fig.update_traces(line_width=2.5, opacity=0.75)

    elif chart_type == 'funnel':
        fig = px.funnel(df, x=y_col, y=x_col, color_discrete_sequence=palette)

    else:
        fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=palette)

    return fig
