import os
import uuid
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from django.conf import settings

# Color palette
PRIMARY = '#1F3864'
ACCENT = '#C9A84C'
PALETTE = [PRIMARY, ACCENT, '#2E75B6', '#ED7D31', '#70AD47', '#9E480E', '#636363']


def build_chart(chart_config: dict, df: pd.DataFrame, output_dir: str = None) -> str:
    """Build a Plotly chart and export as PNG. Returns relative path from MEDIA_ROOT."""
    if output_dir is None:
        output_dir = str(settings.MEDIA_ROOT / 'charts')
    os.makedirs(output_dir, exist_ok=True)

    # Apply filter if specified
    filter_expr = chart_config.get('filter_expr')
    if filter_expr:
        try:
            df = df.query(filter_expr)
        except Exception:
            pass

    # Apply top_n limit
    top_n = chart_config.get('top_n')
    x_col = chart_config.get('x_col', '')
    y_cols = chart_config.get('y_cols', [])
    color_col = chart_config.get('color_col')
    title = chart_config.get('title', '')
    sort_by = chart_config.get('sort_by')
    chart_type = chart_config.get('chart_type', 'bar_chart')

    # Validate columns exist — case-insensitive fuzzy match
    def _match_col(name, columns):
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
        return ''

    y_col = y_cols[0]

    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)
    if top_n:
        df = df.head(top_n)

    fig = _build_figure(chart_type, df, x_col, y_cols, y_col, color_col, title, chart_config)

    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Calibri, Arial', size=13, color='#2F2F2F'),
        title=dict(text=title, font=dict(size=16, color=PRIMARY), x=0.05),
        margin=dict(l=60, r=30, t=60, b=60),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )

    filename = f"chart_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(output_dir, filename)
    fig.write_image(filepath, width=900, height=500, scale=1.5)
    return f"charts/{filename}", fig.to_json()


def _build_figure(chart_type, df, x_col, y_cols, y_col, color_col, title, config):
    if chart_type == 'bar_chart':
        fig = px.bar(df, x=x_col, y=y_col, color=color_col,
                     color_discrete_sequence=PALETTE, text_auto='.2s')
        fig.update_traces(textposition='outside')

    elif chart_type == 'line_chart':
        if color_col and color_col in df.columns:
            fig = px.line(df, x=x_col, y=y_col, color=color_col,
                          color_discrete_sequence=PALETTE, markers=True)
        else:
            fig = px.line(df, x=x_col, y=y_col,
                          color_discrete_sequence=PALETTE, markers=True)

    elif chart_type == 'scatter':
        fig = px.scatter(df, x=x_col, y=y_col, color=color_col,
                         color_discrete_sequence=PALETTE, size_max=15)

    elif chart_type == 'pie_chart':
        fig = px.pie(df, names=x_col, values=y_col,
                     color_discrete_sequence=PALETTE, hole=0.35)
        fig.update_traces(textposition='inside', textinfo='percent+label')

    elif chart_type == 'heatmap':
        try:
            pivot = df.pivot_table(index=x_col, columns=color_col or y_cols[1] if len(y_cols) > 1 else x_col, values=y_col)
            fig = px.imshow(pivot, color_continuous_scale='Blues', text_auto='.1f')
        except Exception:
            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=PALETTE)

    elif chart_type == 'grouped_bar':
        if len(y_cols) > 1:
            fig = px.bar(df, x=x_col, y=y_cols, barmode='group',
                         color_discrete_sequence=PALETTE)
        elif color_col and color_col in df.columns:
            fig = px.bar(df, x=x_col, y=y_col, color=color_col, barmode='group',
                         color_discrete_sequence=PALETTE)
        else:
            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=PALETTE)

    elif chart_type == 'waterfall':
        # Simple waterfall using bar with positive/negative color coding
        if pd.api.types.is_numeric_dtype(df[y_col]):
            colors = [ACCENT if v >= 0 else '#C00000' for v in df[y_col]]
            fig = go.Figure(go.Bar(x=df[x_col].astype(str), y=df[y_col],
                                    marker_color=colors, text=df[y_col].round(1),
                                    textposition='outside'))
            fig.update_layout(title_text=title)
        else:
            fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=PALETTE)

    else:
        fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=PALETTE)

    return fig
