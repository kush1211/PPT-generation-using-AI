from django.urls import path
from .views import (
    ProjectListCreateView, ProjectDetailView,
    UploadDataView, UploadDocumentView, ProfileView,
    InferObjectivesView, ObjectivesView,
    GenerateView, SlidesView, DownloadView,
    ChatView, PdfExportView,
)

urlpatterns = [
    path('projects/', ProjectListCreateView.as_view(), name='projects'),
    path('projects/<uuid:pk>/', ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<uuid:pk>/upload-data/', UploadDataView.as_view(), name='upload-data'),
    path('projects/<uuid:pk>/upload-document/', UploadDocumentView.as_view(), name='upload-document'),
    path('projects/<uuid:pk>/profile/', ProfileView.as_view(), name='profile'),
    path('projects/<uuid:pk>/infer-objectives/', InferObjectivesView.as_view(), name='infer-objectives'),
    path('projects/<uuid:pk>/objectives/', ObjectivesView.as_view(), name='objectives'),
    path('projects/<uuid:pk>/generate/', GenerateView.as_view(), name='generate'),
    path('projects/<uuid:pk>/slides/', SlidesView.as_view(), name='slides'),
    path('projects/<uuid:pk>/download/', DownloadView.as_view(), name='download'),
    path('projects/<uuid:pk>/pdf/', PdfExportView.as_view(), name='pdf-export'),
    path('projects/<uuid:pk>/chat/', ChatView.as_view(), name='chat'),
]
