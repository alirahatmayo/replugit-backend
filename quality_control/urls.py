from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'quality-controls', views.QualityControlViewSet)
router.register(r'unit-qc', views.ProductUnitQCViewSet)

app_name = 'quality_control'

urlpatterns = [
    path('', include(router.urls)),
]