from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for DRF viewsets
router = DefaultRouter()
router.register(r'items', views.ManifestItemViewSet)
router.register(r'groups', views.ManifestGroupViewSet, basename='manifestgroup')
router.register(r'templates', views.ManifestTemplateViewSet)
router.register(r'mappings', views.ManifestColumnMappingViewSet)
router.register(r'', views.ManifestViewSet)

app_name = 'manifest'

# Define direct URL patterns first, before including router URLs
direct_patterns = [
    # Add custom API views
    path('process/', views.ProcessManifestAPIView.as_view(), name='process-manifest'),
    path('download/', views.DownloadManifestAPIView.as_view(), name='download-manifest'),
    
    # Add standalone view for download_remapped with a very explicit pattern
    path('manifest/<int:pk>/download-remapped-file/', views.DownloadRemappedManifestView.as_view(), name='download-remapped-manifest'),
      # Add a test endpoint for diagnosing download issues
    path('test-download/<int:pk>/', views.TestDownloadView.as_view(), name='test-download'),
]

urlpatterns = direct_patterns + [
    # Include routes from the DefaultRouter
    path('', include(router.urls)),
]
