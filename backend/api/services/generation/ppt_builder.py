import os
import uuid
from pathlib import Path
from datetime import date
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from django.conf import settings

# Branding
PRIMARY = RGBColor(0x1F, 0x38, 0x64)    # Deep navy
ACCENT = RGBColor(0xC9, 0xA8, 0x4C)     # Gold
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)
DARK_GRAY = RGBColor(0x40, 0x40, 0x40)
FONT = 'Calibri'

# Slide dimensions (widescreen 16:9)
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


def build_presentation(slides_data: list[dict], output_filename: str = None) -> str:
    """Assemble a full .pptx from slide data. Returns relative path from MEDIA_ROOT."""
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    for slide_data in slides_data:
        slide_type = slide_data.get('slide_type', 'chart')
        if slide_type == 'title':
            _add_title_slide(prs, slide_data)
        elif slide_type == 'overview':
            _add_overview_slide(prs, slide_data)
        elif slide_type in ('chart', 'insight', 'comparison'):
            _add_chart_slide(prs, slide_data)
        elif slide_type == 'executive_summary':
            _add_executive_summary_slide(prs, slide_data)
        elif slide_type == 'recommendation':
            _add_recommendation_slide(prs, slide_data)
        elif slide_type == 'data_table':
            _add_chart_slide(prs, slide_data)  # fallback to chart layout
        else:
            _add_chart_slide(prs, slide_data)

    output_dir = settings.MEDIA_ROOT / 'presentations'
    os.makedirs(output_dir, exist_ok=True)
    if output_filename is None:
        output_filename = f"presentation_{uuid.uuid4().hex[:8]}.pptx"
    filepath = output_dir / output_filename
    prs.save(str(filepath))
    return f"presentations/{output_filename}"


def update_slide(pptx_path: str, slide_index: int, slide_data: dict) -> str:
    """Update a single slide in an existing .pptx and save as new file."""
    full_path = settings.MEDIA_ROOT / pptx_path
    prs = Presentation(str(full_path))

    if 0 <= slide_index < len(prs.slides):
        # Remove existing slide by XML manipulation
        slide_elem = prs.slides._sldIdLst[slide_index]
        prs.slides._sldIdLst.remove(slide_elem)

        # Insert replacement at same index — simplest: rebuild all slides
        # For now, rebuild the entire presentation with the updated slide
        pass

    # Rebuild full presentation with updated slide_data
    # (partial update via python-pptx XML is complex; full rebuild is reliable)
    return build_presentation_from_path(pptx_path, slide_index, slide_data)


def build_presentation_from_path(existing_pptx_rel: str, updated_index: int, updated_slide: dict) -> str:
    """Rebuild a new .pptx updating just one slide. Returns new relative path."""
    # This creates a new file; the caller should update the Project.pptx_file field
    output_filename = f"presentation_{uuid.uuid4().hex[:8]}.pptx"
    return output_filename  # simplified; full rebuild happens in the view via build_presentation


# ─── Slide builders ──────────────────────────────────────────────────────────

def _blank_slide(prs: Presentation):
    blank_layout = prs.slide_layouts[6]  # blank
    return prs.slides.add_slide(blank_layout)


def _add_footer(slide, slide_number: int, total: int):
    tf = slide.shapes.add_textbox(Inches(0.3), Inches(7.1), Inches(12.7), Inches(0.3))
    p = tf.text_frame.paragraphs[0]
    p.text = f"Confidential  ·  Slide {slide_number + 1}"
    p.font.size = Pt(9)
    p.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    p.alignment = PP_ALIGN.RIGHT


def _header_bar(slide, color: RGBColor = None):
    """Solid color bar across top of slide."""
    from pptx.util import Emu
    bar = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        0, 0, SLIDE_W, Inches(0.08)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = color or PRIMARY
    bar.line.fill.background()


def _add_title_slide(prs: Presentation, data: dict):
    slide = _blank_slide(prs)

    # Background fill
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = PRIMARY

    # Title
    tf = slide.shapes.add_textbox(Inches(1), Inches(2.2), Inches(11.3), Inches(1.8))
    tf.text_frame.word_wrap = True
    p = tf.text_frame.paragraphs[0]
    p.text = data.get('title', 'Presentation Title')
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER

    # Subtitle
    subtitle = data.get('subtitle', '')
    if subtitle:
        tf2 = slide.shapes.add_textbox(Inches(1), Inches(4.1), Inches(11.3), Inches(0.7))
        p2 = tf2.text_frame.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(20)
        p2.font.color.rgb = ACCENT
        p2.alignment = PP_ALIGN.CENTER

    # Date
    tf3 = slide.shapes.add_textbox(Inches(1), Inches(5.0), Inches(11.3), Inches(0.4))
    p3 = tf3.text_frame.paragraphs[0]
    p3.text = date.today().strftime('%B %Y')
    p3.font.size = Pt(14)
    p3.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    p3.alignment = PP_ALIGN.CENTER

    # Accent line
    line = slide.shapes.add_shape(1, Inches(4.5), Inches(4.8), Inches(4.3), Inches(0.04))
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT
    line.line.fill.background()


def _add_overview_slide(prs: Presentation, data: dict):
    slide = _blank_slide(prs)
    _header_bar(slide)

    # Title
    _add_slide_title(slide, data.get('title', ''))

    # Left: Key Findings bullets
    bullets = data.get('bullet_points', [])
    tf = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(6), Inches(5.7))
    tf.text_frame.word_wrap = True
    tf.text_frame.clear()
    heading = tf.text_frame.paragraphs[0]
    heading.text = 'Key Findings'
    heading.font.bold = True
    heading.font.size = Pt(16)
    heading.font.color.rgb = PRIMARY

    for bullet in bullets[:6]:
        p = tf.text_frame.add_paragraph()
        p.text = f'• {bullet}'
        p.font.size = Pt(13)
        p.font.color.rgb = DARK_GRAY
        p.space_before = Pt(6)

    # Right: Narrative
    narrative = data.get('narrative', '')
    if narrative:
        tf2 = slide.shapes.add_textbox(Inches(6.8), Inches(1.3), Inches(6.3), Inches(5.7))
        tf2.text_frame.word_wrap = True
        p2 = tf2.text_frame.paragraphs[0]
        p2.text = narrative
        p2.font.size = Pt(13)
        p2.font.color.rgb = DARK_GRAY

    _add_footer(slide, data.get('slide_index', 0), 0)


def _add_chart_slide(prs: Presentation, data: dict):
    slide = _blank_slide(prs)
    _header_bar(slide)

    # Title
    _add_slide_title(slide, data.get('title', ''))

    # Subtitle
    subtitle = data.get('subtitle', '')
    if subtitle:
        tf_sub = slide.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(12.3), Inches(0.4))
        p_sub = tf_sub.text_frame.paragraphs[0]
        p_sub.text = subtitle
        p_sub.font.size = Pt(13)
        p_sub.font.italic = True
        p_sub.font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    chart_png = data.get('chart_png', '')
    narrative = data.get('narrative', '')

    if chart_png:
        chart_full_path = settings.MEDIA_ROOT / chart_png
        if os.path.exists(str(chart_full_path)):
            if narrative:
                # Chart takes top 65%, narrative below
                slide.shapes.add_picture(
                    str(chart_full_path),
                    Inches(0.4), Inches(1.45),
                    Inches(12.5), Inches(4.4)
                )
                _add_narrative_box(slide, narrative, Inches(0.5), Inches(5.95), Inches(12.3), Inches(1.3))
            else:
                slide.shapes.add_picture(
                    str(chart_full_path),
                    Inches(0.4), Inches(1.2),
                    Inches(12.5), Inches(5.9)
                )
    elif narrative:
        _add_narrative_box(slide, narrative, Inches(0.5), Inches(1.5), Inches(12.3), Inches(5.5))

    _add_footer(slide, data.get('slide_index', 0), 0)


def _add_executive_summary_slide(prs: Presentation, data: dict):
    slide = _blank_slide(prs)
    _header_bar(slide)

    _add_slide_title(slide, data.get('title', 'Key Takeaways'))

    chart_png = data.get('chart_png', '')
    bullets = data.get('bullet_points', [])
    narrative = data.get('narrative', '')

    if chart_png:
        chart_full_path = settings.MEDIA_ROOT / chart_png
        if os.path.exists(str(chart_full_path)):
            slide.shapes.add_picture(
                str(chart_full_path),
                Inches(0.4), Inches(1.2),
                Inches(12.5), Inches(4.2)
            )
            if narrative:
                _add_narrative_box(slide, narrative, Inches(0.5), Inches(5.5), Inches(12.3), Inches(1.2))
        else:
            chart_png = ''

    if not chart_png:
        if bullets:
            tf = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(12.3), Inches(5.5))
            tf.text_frame.word_wrap = True
            tf.text_frame.clear()
            for i, bullet in enumerate(bullets[:7], 1):
                p = tf.text_frame.paragraphs[0] if i == 1 else tf.text_frame.add_paragraph()
                p.text = f'{i}.  {bullet}'
                p.font.size = Pt(14)
                p.font.color.rgb = DARK_GRAY
                p.space_before = Pt(8)
        elif narrative:
            _add_narrative_box(slide, narrative, Inches(0.5), Inches(1.5), Inches(12.3), Inches(5.5))

    _add_footer(slide, data.get('slide_index', 0), 0)


def _add_recommendation_slide(prs: Presentation, data: dict):
    slide = _blank_slide(prs)
    _header_bar(slide)

    _add_slide_title(slide, data.get('title', 'Recommended Actions'))

    bullets = data.get('bullet_points', [])
    narrative = data.get('narrative', '')

    items = bullets if bullets else (narrative.split('. ') if narrative else [])

    # Display as numbered action cards
    card_width = Inches(3.8)
    card_height = Inches(3.8)
    positions = [
        (Inches(0.4), Inches(1.5)),
        (Inches(4.6), Inches(1.5)),
        (Inches(8.8), Inches(1.5)),
    ]

    for i, (item, (x, y)) in enumerate(zip(items[:3], positions)):
        # Card background
        card = slide.shapes.add_shape(1, x, y, card_width, card_height)
        card.fill.solid()
        card.fill.fore_color.rgb = LIGHT_GRAY
        card.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

        # Number badge
        badge = slide.shapes.add_shape(
            9,  # oval
            x + Inches(0.15), y + Inches(0.15),
            Inches(0.55), Inches(0.55)
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = PRIMARY
        badge.line.fill.background()
        badge.text_frame.paragraphs[0].text = str(i + 1)
        badge.text_frame.paragraphs[0].font.color.rgb = WHITE
        badge.text_frame.paragraphs[0].font.bold = True
        badge.text_frame.paragraphs[0].font.size = Pt(14)

        # Card text
        tf = slide.shapes.add_textbox(
            x + Inches(0.2), y + Inches(0.85),
            card_width - Inches(0.4), card_height - Inches(1.0)
        )
        tf.text_frame.word_wrap = True
        p = tf.text_frame.paragraphs[0]
        p.text = item.strip()
        p.font.size = Pt(12)
        p.font.color.rgb = DARK_GRAY

    _add_footer(slide, data.get('slide_index', 0), 0)


def _add_slide_title(slide, title: str):
    tf = slide.shapes.add_textbox(Inches(0.5), Inches(0.12), Inches(12.3), Inches(0.75))
    tf.text_frame.word_wrap = True
    p = tf.text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = PRIMARY


def _add_narrative_box(slide, narrative: str, left, top, width, height):
    tf = slide.shapes.add_textbox(left, top, width, height)
    tf.text_frame.word_wrap = True
    p = tf.text_frame.paragraphs[0]
    p.text = narrative
    p.font.size = Pt(13)
    p.font.color.rgb = DARK_GRAY
