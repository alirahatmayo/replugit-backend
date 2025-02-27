from rest_framework.routers import DefaultRouter
from .views import WarrantyViewSet
from django.urls import path, include

router = DefaultRouter()
router.register(r'warranties', WarrantyViewSet, basename='warranty')

# URL Patterns
urlpatterns = [
    path('', include(router.urls)),
]
