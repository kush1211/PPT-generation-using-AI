from rest_framework import serializers
from .models import Project, DataFile, RFPDocument, ObjectivesConfig, Insight, Slide, ChatMessage


class DataFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataFile
        fields = ['id', 'file_type', 'column_map', 'profile', 'created_at']


class RFPDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFPDocument
        fields = ['id', 'file_type', 'parsed_text', 'created_at']


class ObjectivesConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectivesConfig
        fields = [
            'id', 'presentation_title', 'audience', 'tone',
            'primary_objectives', 'key_metrics', 'comparison_dimensions',
            'created_at', 'updated_at',
        ]


class InsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insight
        fields = [
            'id', 'insight_id', 'title', 'finding', 'magnitude',
            'data_slice', 'chart_hint', 'priority', 'created_at',
        ]


class SlideSerializer(serializers.ModelSerializer):
    chart_png_url = serializers.SerializerMethodField()

    class Meta:
        model = Slide
        fields = [
            'id', 'slide_index', 'slide_type', 'title', 'subtitle',
            'narrative', 'chart_png_url', 'chart_json', 'bullet_points', 'speaker_notes',
            'insight_ids', 'chart_config', 'created_at', 'updated_at',
        ]

    def get_chart_png_url(self, obj):
        if obj.chart_png:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.chart_png.url)
            return obj.chart_png.url
        return None


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'slide_index_affected', 'created_at']


class ProjectSerializer(serializers.ModelSerializer):
    data_file = DataFileSerializer(read_only=True)
    rfp_document = RFPDocumentSerializer(read_only=True)
    objectives = ObjectivesConfigSerializer(read_only=True)
    pptx_url = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'status', 'pptx_url',
            'data_file', 'rfp_document', 'objectives',
            'created_at', 'updated_at',
        ]

    def get_pptx_url(self, obj):
        if obj.pptx_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pptx_file.url)
            return obj.pptx_file.url
        return None


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'title', 'status', 'created_at']
