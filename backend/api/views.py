import os
import json
import pandas as pd
from pathlib import Path

from django.http import FileResponse, Http404, HttpResponse
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import (
    Project, DataFile, RFPDocument, ObjectivesConfig,
    BriefDecomposition, SheetGroup, Insight, Slide, ChatMessage, TokenUsageLog,
)
from .serializers import (
    ProjectSerializer, ProjectCreateSerializer, DataFileSerializer,
    RFPDocumentSerializer, ObjectivesConfigSerializer, InsightSerializer,
    SlideSerializer, ChatMessageSerializer,
)
from .services.data_ingestion.csv_excel_loader import load_file
from .services.data_ingestion.document_parser import parse_document
from .services.data_ingestion.data_profiler import profile_dataframe
from .services.data_ingestion.multi_sheet_loader import load_all_sheets, extract_sheet_metadata
from .services.analysis.objective_inferrer import infer_objectives
from .services.analysis.brief_decomposer import decompose_brief
from .services.analysis.insight_extractor import extract_insights
from .services.analysis.chart_selector import select_chart_config
from .services.generation.slide_planner import plan_slides
from .services.generation.narrative_writer import write_narrative
from .services.generation.chart_builder import build_chart
from .services.generation.ppt_builder import build_presentation
from .services.generation.pipeline_orchestrator import run_generation_pipeline
from .services.chat.intent_classifier import classify_intent
from .services.chat.chat_handler import handle_chat


class ProjectListCreateView(APIView):
    def get(self, request):
        projects = Project.objects.all().order_by('-created_at')
        serializer = ProjectSerializer(projects, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        title = request.data.get('title', '')
        project = Project.objects.create(title=title, status='uploading')
        serializer = ProjectCreateSerializer(project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    def get_object(self, pk):
        try:
            return Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        project = self.get_object(pk)
        serializer = ProjectSerializer(project, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, pk):
        project = self.get_object(pk)
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadDataView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)

        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        ext = Path(file.name).suffix.lower()
        if ext not in ('.csv', '.xlsx', '.xls'):
            return Response({'error': 'Only CSV and Excel files are supported'}, status=400)

        data_file, _ = DataFile.objects.get_or_create(project=project)
        data_file.file = file
        data_file.file_type = 'csv' if ext == '.csv' else 'excel'
        data_file.save()

        file_path = str(settings.MEDIA_ROOT / data_file.file.name)

        # New pipeline: load all sheets and extract per-sheet metadata (Step 1)
        sheet_dfs = load_all_sheets(file_path)
        sheet_metadata = extract_sheet_metadata(sheet_dfs)
        data_file.sheet_metadata = sheet_metadata

        # Backward compat: profile the primary (largest) sheet for chat handler
        from .services.data_ingestion.multi_sheet_loader import get_primary_sheet
        primary_df = get_primary_sheet(sheet_dfs)
        from .services.data_ingestion.csv_excel_loader import _infer_column_types
        column_map = _infer_column_types(primary_df)
        profile = profile_dataframe(primary_df, column_map)
        data_file.column_map = column_map
        data_file.profile = profile
        data_file.save()

        project.status = 'uploaded'
        project.save()

        return Response({
            'column_map': column_map,
            'sheet_count': len(sheet_dfs),
            'sheet_names': list(sheet_dfs.keys()),
            'profile': {
                'shape': profile['shape'],
                'columns': profile['columns'],
                'condensed_repr': profile['condensed_repr'],
                'sample_rows': profile['sample_rows'],
                'column_summary': profile['column_summary'],
            }
        })


class UploadDocumentView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)

        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        ext = Path(file.name).suffix.lower()
        if ext not in ('.pdf', '.docx', '.txt'):
            return Response({'error': 'Only PDF, DOCX, and TXT files are supported'}, status=400)

        rfp_doc, _ = RFPDocument.objects.get_or_create(project=project)
        rfp_doc.file = file
        rfp_doc.file_type = ext[1:]
        rfp_doc.save()

        file_path = str(settings.MEDIA_ROOT / rfp_doc.file.name)
        parsed_text = parse_document(file_path)
        rfp_doc.parsed_text = parsed_text
        rfp_doc.save()

        return Response({'parsed_length': len(parsed_text), 'preview': parsed_text[:300]})


class ProfileView(APIView):
    def get(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
            profile = project.data_file.profile
            column_map = project.data_file.column_map
            return Response({'profile': profile, 'column_map': column_map})
        except (Project.DoesNotExist, DataFile.DoesNotExist):
            return Response({'error': 'Not found'}, status=404)


class InferObjectivesView(APIView):
    def post(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)

        try:
            data_file = project.data_file
        except DataFile.DoesNotExist:
            return Response({'error': 'Upload data file first'}, status=400)

        rfp_text = ''
        try:
            rfp_text = project.rfp_document.parsed_text
        except RFPDocument.DoesNotExist:
            pass

        # Step 0: Brief Decomposition (replaces infer_objectives)
        sheet_metadata = data_file.sheet_metadata or {}
        if not sheet_metadata:
            # Fallback: build minimal metadata summary from legacy profile
            condensed_repr = data_file.profile.get('condensed_repr', '')
            sheet_metadata = {'Sheet1': {'columns': list(data_file.column_map.get('metrics', []) +
                                                          data_file.column_map.get('dimensions', []) +
                                                          data_file.column_map.get('dates', [])),
                                          'row_count': data_file.profile.get('shape', [0])[0],
                                          'sample_top': data_file.profile.get('sample_rows', [])[:2],
                                          'inferred_dtypes': {}, 'unique_counts': {}, 'null_pct': {}}}

        result = decompose_brief(rfp_text, sheet_metadata)

        # Persist BriefDecomposition
        BriefDecomposition.objects.update_or_create(
            project=project,
            defaults={
                'domain_context': result.get('domain_context', ''),
                'analytical_questions': result.get('analytical_questions', []),
                'audience_and_tone': result.get('audience_and_tone', ''),
                'full_summary': result.get('full_summary', ''),
            }
        )

        # Also persist ObjectivesConfig for backward compat (audience/tone/title)
        obj, _ = ObjectivesConfig.objects.update_or_create(
            project=project,
            defaults={
                'presentation_title': result.get('presentation_title', 'Presentation'),
                'audience': result.get('audience', 'executive'),
                'tone': result.get('tone', 'formal'),
                'primary_objectives': [],
                'key_metrics': [],
                'comparison_dimensions': [],
            }
        )

        project.status = 'configured'
        project.save()

        # Return combined response (superset of old ObjectivesConfigSerializer shape)
        response_data = ObjectivesConfigSerializer(obj).data
        response_data['brief'] = {
            'domain_context': result.get('domain_context', ''),
            'analytical_questions': result.get('analytical_questions', []),
            'audience_and_tone': result.get('audience_and_tone', ''),
            'full_summary': result.get('full_summary', ''),
        }
        return Response(response_data)


class ObjectivesView(APIView):
    def get(self, request, pk):
        try:
            obj = ObjectivesConfig.objects.get(project_id=pk)
            return Response(ObjectivesConfigSerializer(obj).data)
        except ObjectivesConfig.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

    def put(self, request, pk):
        try:
            obj = ObjectivesConfig.objects.get(project_id=pk)
        except ObjectivesConfig.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        serializer = ObjectivesConfigSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            Project.objects.filter(pk=pk).update(status='configured')
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class GenerateView(APIView):
    def post(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)

        try:
            data_file = project.data_file
        except DataFile.DoesNotExist:
            return Response({'error': 'Upload data file first'}, status=400)

        try:
            project.objectives
        except ObjectivesConfig.DoesNotExist:
            return Response({'error': 'Configure objectives first'}, status=400)

        try:
            project.brief
        except BriefDecomposition.DoesNotExist:
            return Response({'error': 'Run "Infer Objectives" first to decompose the brief'}, status=400)

        project.status = 'generating'
        project.save()

        try:
            result = run_generation_pipeline(project)
            pptx_rel_path = result['pptx_path']
            return Response({
                'status': 'ready',
                'slide_count': result['slide_count'],
                'pptx_url': request.build_absolute_uri(f'/media/{pptx_rel_path}'),
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            project.status = 'error'
            project.save()
            return Response({'error': str(e)}, status=500)


class SlidesView(APIView):
    def get(self, request, pk):
        slides = Slide.objects.filter(project_id=pk).order_by('slide_index')
        serializer = SlideSerializer(slides, many=True, context={'request': request})
        return Response(serializer.data)


class DownloadView(APIView):
    def get(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if not project.pptx_file:
            return Response({'error': 'No presentation generated yet'}, status=404)

        file_path = settings.MEDIA_ROOT / project.pptx_file.name
        if not file_path.exists():
            return Response({'error': 'File not found on disk'}, status=404)

        title = project.title or 'presentation'
        return FileResponse(
            open(str(file_path), 'rb'),
            content_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            as_attachment=True,
            filename=f'{title}.pptx',
        )


class ChatView(APIView):
    def post(self, request, pk):
        try:
            project = Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        user_message = request.data.get('message', '').strip()
        if not user_message:
            return Response({'error': 'Empty message'}, status=400)

        ChatMessage.objects.create(project=project, role='user', content=user_message)

        slides = list(Slide.objects.filter(project=project).order_by('slide_index').values())
        chat_history = list(
            ChatMessage.objects.filter(project=project)
            .order_by('created_at').values('role', 'content')
        )

        intent = classify_intent(user_message, slides, chat_history)
        intent['_user_message'] = user_message

        result = handle_chat(intent, project, slides, chat_history)

        response_text = result.get('response_text', '')
        updated_slide_index = result.get('updated_slide_index')
        slide_data = result.get('slide_data')
        is_new_slide = result.get('is_new_slide', False)

        pptx_url = None
        if slide_data is not None:
            if is_new_slide:
                new_slide = Slide.objects.create(
                    project=project,
                    slide_index=slide_data.get('slide_index', len(slides)),
                    slide_type=slide_data.get('slide_type', 'chart'),
                    title=slide_data.get('title', ''),
                    subtitle=slide_data.get('subtitle', ''),
                    narrative=slide_data.get('narrative', ''),
                    bullet_points=slide_data.get('bullet_points', []),
                    speaker_notes=slide_data.get('speaker_notes', ''),
                    insight_ids=slide_data.get('insight_ids', []),
                    chart_config=slide_data.get('chart_config', {}),
                )
                if slide_data.get('chart_png'):
                    new_slide.chart_png = slide_data['chart_png']
                    new_slide.save()
            else:
                new_narrative = result.get('new_narrative', '')
                if updated_slide_index is not None and new_narrative:
                    Slide.objects.filter(
                        project=project, slide_index=updated_slide_index
                    ).update(narrative=new_narrative)

            # Rebuild PPT with all slides
            all_slides = list(Slide.objects.filter(project=project).order_by('slide_index'))
            slides_for_ppt = [
                {
                    'slide_index': s.slide_index,
                    'slide_type': s.slide_type,
                    'title': s.title,
                    'subtitle': s.subtitle,
                    'narrative': s.narrative,
                    'chart_png': str(s.chart_png) if s.chart_png else '',
                    'bullet_points': s.bullet_points,
                    'speaker_notes': s.speaker_notes,
                    'insight_ids': s.insight_ids,
                    'chart_config': s.chart_config,
                }
                for s in all_slides
            ]
            pptx_rel_path = build_presentation(slides_for_ppt)
            project.pptx_file = pptx_rel_path
            project.save()
            pptx_url = request.build_absolute_uri(f'/media/{pptx_rel_path}')

        ChatMessage.objects.create(
            project=project,
            role='assistant',
            content=response_text,
            slide_index_affected=updated_slide_index,
        )

        return Response({
            'message': response_text,
            'updated_slide_index': updated_slide_index,
            'slide_data': slide_data,
            'pptx_url': pptx_url,
        })

    def get(self, request, pk):
        messages = ChatMessage.objects.filter(project_id=pk).order_by('created_at')
        return Response(ChatMessageSerializer(messages, many=True).data)


class PdfExportView(APIView):
    def get(self, request, pk):
        try:
            Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        from playwright.sync_api import sync_playwright
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        url = f"{frontend_url}/print/{pk}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(url, wait_until='networkidle', timeout=30000)
                # Extra wait for Plotly charts to finish rendering
                page.wait_for_timeout(1500)
                pdf_bytes = page.pdf(
                    format='A4',
                    landscape=True,
                    print_background=True,
                    margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
                )
                browser.close()
        except Exception as e:
            return Response({'error': f'PDF generation failed: {e}'}, status=500)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="presentation_{pk}.pdf"'
        return response


class TokenUsageLogView(APIView):
    """GET /api/token-usage/  — list all token usage logs, newest first.
    Each entry represents one full generation pipeline run.
    created_at_ist is the timestamp converted to Asia/Kolkata (IST = UTC+5:30).
    """
    def get(self, request):
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        logs = TokenUsageLog.objects.select_related('project').order_by('-created_at')
        data = [
            {
                "id": log.id,
                "project_id": str(log.project_id),
                "project_title": log.project.title or "Untitled",
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "slide_count": log.slide_count,
                "duration_seconds": log.duration_seconds,
                "created_at_ist": log.created_at.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            }
            for log in logs
        ]
        return Response(data)
