# products/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, ProductUnitViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'product-units', ProductUnitViewSet)

# URL Patterns
urlpatterns = [
    path('', include(router.urls)),
]
