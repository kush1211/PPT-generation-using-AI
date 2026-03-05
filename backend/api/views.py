import os
import json
import pandas as pd
from pathlib import Path

from django.http import FileResponse, Http404
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Project, DataFile, RFPDocument, ObjectivesConfig, Insight, Slide, ChatMessage
from .serializers import (
    ProjectSerializer, ProjectCreateSerializer, DataFileSerializer,
    RFPDocumentSerializer, ObjectivesConfigSerializer, InsightSerializer,
    SlideSerializer, ChatMessageSerializer,
)
from .services.data_ingestion.csv_excel_loader import load_file
from .services.data_ingestion.document_parser import parse_document
from .services.data_ingestion.data_profiler import profile_dataframe
from .services.analysis.objective_inferrer import infer_objectives
from .services.analysis.insight_extractor import extract_insights
from .services.analysis.chart_selector import select_chart_config
from .services.generation.slide_planner import plan_slides
from .services.generation.narrative_writer import write_narrative
from .services.generation.chart_builder import build_chart
from .services.generation.ppt_builder import build_presentation
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
        df, column_map = load_file(file_path)
        profile = profile_dataframe(df, column_map)

        data_file.column_map = column_map
        data_file.profile = profile
        data_file.save()

        project.status = 'uploaded'
        project.save()

        return Response({
            'column_map': column_map,
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

        condensed_repr = data_file.profile.get('condensed_repr', '')
        rfp_text = ''
        try:
            rfp_text = project.rfp_document.parsed_text
        except RFPDocument.DoesNotExist:
            pass

        result = infer_objectives(rfp_text, condensed_repr)

        obj, _ = ObjectivesConfig.objects.update_or_create(
            project=project,
            defaults={
                'presentation_title': result.get('presentation_title', 'Presentation'),
                'audience': result.get('audience', 'executive'),
                'tone': result.get('tone', 'formal'),
                'primary_objectives': result.get('primary_objectives', []),
                'key_metrics': result.get('key_metrics', []),
                'comparison_dimensions': result.get('comparison_dimensions', []),
            }
        )

        project.status = 'configured'
        project.save()

        return Response(ObjectivesConfigSerializer(obj).data)


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
            objectives_obj = project.objectives
        except (DataFile.DoesNotExist, ObjectivesConfig.DoesNotExist):
            return Response({'error': 'Upload data and configure objectives first'}, status=400)

        project.status = 'generating'
        project.save()

        try:
            profile = data_file.profile
            column_map = data_file.column_map
            condensed_repr = profile.get('condensed_repr', '')
            column_summary = profile.get('column_summary', {})

            objectives = {
                'presentation_title': objectives_obj.presentation_title,
                'audience': objectives_obj.audience,
                'tone': objectives_obj.tone,
                'primary_objectives': objectives_obj.primary_objectives,
                'key_metrics': objectives_obj.key_metrics,
                'comparison_dimensions': objectives_obj.comparison_dimensions,
            }

            file_path = str(settings.MEDIA_ROOT / data_file.file.name)
            df, _ = load_file(file_path)

            # 1. Extract insights
            insights_data = extract_insights(condensed_repr, objectives, column_summary)
            Insight.objects.filter(project=project).delete()
            for ins in insights_data:
                Insight.objects.create(
                    project=project,
                    insight_id=ins['insight_id'],
                    title=ins['title'],
                    finding=ins['finding'],
                    magnitude=ins['magnitude'],
                    data_slice=ins.get('data_slice', {}),
                    chart_hint=ins['chart_hint'],
                    priority=ins['priority'],
                )

            # 2. Plan slides
            slide_plan = plan_slides(insights_data, objectives)

            # 3. Generate content per slide
            Slide.objects.filter(project=project).delete()
            slides_for_ppt = []
            insight_map = {ins['insight_id']: ins for ins in insights_data}

            for item in slide_plan:
                slide_type = item.get('slide_type', 'chart')
                slide_title = item.get('title', '')
                narrative_hint = item.get('narrative_hint', '')
                insight_ids = item.get('insight_ids', [])
                bullet_points = item.get('bullet_points', [])
                slide_idx = item.get('slide_index', 0)

                primary_insight = next(
                    (insight_map[iid] for iid in insight_ids if iid in insight_map), None
                )

                chart_path = ''
                chart_config = {}

                if slide_type not in ('title',) and primary_insight:
                    try:
                        chart_config = select_chart_config(primary_insight, column_map, slide_title)
                        chart_path = build_chart(chart_config, df)
                    except Exception:
                        pass

                narrative = ''
                if slide_type != 'title':
                    try:
                        insight_for_narrative = primary_insight or {
                            'finding': narrative_hint, 'data_slice': {}
                        }
                        narrative = write_narrative(
                            slide_title=slide_title,
                            insight=insight_for_narrative,
                            chart_type=chart_config.get('chart_type', 'bar_chart'),
                            narrative_hint=narrative_hint,
                            audience=objectives_obj.audience,
                            tone=objectives_obj.tone,
                        )
                    except Exception:
                        narrative = narrative_hint

                slide_obj = Slide.objects.create(
                    project=project,
                    slide_index=slide_idx,
                    slide_type=slide_type,
                    title=slide_title,
                    subtitle=item.get('subtitle', ''),
                    narrative=narrative,
                    bullet_points=bullet_points,
                    speaker_notes=narrative_hint,
                    insight_ids=insight_ids,
                    chart_config=chart_config,
                )
                if chart_path:
                    slide_obj.chart_png = chart_path
                    slide_obj.save()

                slides_for_ppt.append({
                    'slide_index': slide_idx,
                    'slide_type': slide_type,
                    'title': slide_title,
                    'subtitle': item.get('subtitle', ''),
                    'narrative': narrative,
                    'chart_png': chart_path,
                    'bullet_points': bullet_points,
                    'speaker_notes': narrative_hint,
                    'insight_ids': insight_ids,
                    'chart_config': chart_config,
                })

            # 4. Assemble PPT
            pptx_rel_path = build_presentation(slides_for_ppt)
            project.pptx_file = pptx_rel_path
            project.status = 'ready'
            project.save()

            return Response({
                'status': 'ready',
                'slide_count': len(slides_for_ppt),
                'pptx_url': request.build_absolute_uri(f'/media/{pptx_rel_path}'),
            })

        except Exception as e:
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
