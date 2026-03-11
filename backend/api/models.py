import uuid
from django.db import models


class Project(models.Model):
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('uploaded', 'Uploaded'),
        ('configured', 'Configured'),
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    pptx_file = models.FileField(upload_to='presentations/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title or 'Untitled'} ({self.status})"


class DataFile(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='data_file')
    file = models.FileField(upload_to='data_files/')
    file_type = models.CharField(max_length=10)  # "csv" | "excel"
    column_map = models.JSONField(default=dict)   # {metrics:[..], dimensions:[..], dates:[..]}
    profile = models.JSONField(default=dict)      # DataProfile serialized (backward compat)
    # New pipeline fields (Step 1 output and downstream)
    sheet_metadata = models.JSONField(default=dict)         # {sheet_name: {columns, samples, row_count, ...}}
    sheet_classifications = models.JSONField(default=dict)  # {sheet_name: {column_roles, irrelevant, summary}}
    relationship_graph = models.JSONField(default=dict)     # {fk_edges, cardinality, join_paths, orphan_sheets}
    summary_stats = models.JSONField(default=dict)          # {group_id: {metrics, dimensions, joins}}
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DataFile for {self.project}"


class RFPDocument(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='rfp_document')
    file = models.FileField(upload_to='rfp_docs/')
    file_type = models.CharField(max_length=10)  # "pdf" | "docx" | "txt"
    parsed_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RFPDocument for {self.project}"


class ObjectivesConfig(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='objectives')
    presentation_title = models.CharField(max_length=255)
    audience = models.CharField(max_length=50)           # "executive" | "analyst" | "client"
    tone = models.CharField(max_length=50)               # "formal" | "consultative" | "technical"
    primary_objectives = models.JSONField(default=list)  # list[str]
    key_metrics = models.JSONField(default=list)         # list[str]
    comparison_dimensions = models.JSONField(default=list)  # list[str]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Objectives for {self.project}"


class BriefDecomposition(models.Model):
    """Step 0 output: decomposes the raw brief into 4 reusable analytical fields."""
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='brief')
    domain_context = models.TextField()              # ~20 tokens, inferred domain
    analytical_questions = models.JSONField(default=list)  # 3-5 analytical questions
    audience_and_tone = models.TextField()           # natural-language audience + tone description
    full_summary = models.TextField()                # 200-300 token synthesis of the brief
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Brief for {self.project}"


class SheetGroup(models.Model):
    """Step 4 output: a logical group of 2-3 sheets with analytical framing."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='sheet_groups')
    group_id = models.CharField(max_length=50)       # "group_0", "group_1", etc.
    sheet_names = models.JSONField(default=list)     # list[str]
    join_keys = models.JSONField(default=dict)        # {sheet_a: col, sheet_b: col}
    analytical_framing = models.TextField(blank=True)
    # Pipeline intermediate results (persisted after each step)
    insight_scan_raw = models.JSONField(default=dict)      # Step 6a: {observations, drill_requests}
    drill_down_results = models.JSONField(default=dict)    # Step 6b: {drill_id: result}
    insights_extracted = models.JSONField(default=list)    # Step 6c: list[insight_dict]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['group_id']

    def __str__(self):
        return f"Group {self.group_id} for {self.project}"


class Insight(models.Model):
    MAGNITUDE_CHOICES = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='insights')
    insight_id = models.CharField(max_length=50)
    title = models.CharField(max_length=500)
    finding = models.TextField()
    magnitude = models.CharField(max_length=10, choices=MAGNITUDE_CHOICES)
    data_slice = models.JSONField(default=dict)
    chart_hint = models.CharField(max_length=50)
    priority = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority']

    def __str__(self):
        return f"Insight: {self.title}"


class Slide(models.Model):
    SLIDE_TYPES = [
        ('title', 'Title'),
        ('overview', 'Overview'),
        ('chart', 'Chart'),
        ('insight', 'Insight'),
        ('comparison', 'Comparison'),
        ('executive_summary', 'Executive Summary'),
        ('recommendation', 'Recommendation'),
        ('data_table', 'Data Table'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='slides')
    slide_index = models.IntegerField()
    slide_type = models.CharField(max_length=30, choices=SLIDE_TYPES)
    title = models.CharField(max_length=500)
    subtitle = models.CharField(max_length=500, blank=True)
    narrative = models.TextField(blank=True)
    chart_png = models.ImageField(upload_to='charts/', null=True, blank=True)
    chart_json = models.TextField(blank=True, default='')
    bullet_points = models.JSONField(default=list)
    speaker_notes = models.TextField(blank=True)
    insight_ids = models.JSONField(default=list)
    chart_config = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slide_index']

    def __str__(self):
        return f"Slide {self.slide_index}: {self.title}"


class TokenUsageLog(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='token_usage_logs')
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    slide_count = models.IntegerField(default=0)
    duration_seconds = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)  # stored UTC, API returns IST

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TokenUsageLog [{self.project}] total={self.total_tokens} slides={self.slide_count}"


class ChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='chat_messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    slide_index_affected = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
