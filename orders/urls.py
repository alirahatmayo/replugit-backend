# orders/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, OrderItemViewSet

router = DefaultRouter()
router.register(r'', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)


# URL Patterns
urlpatterns = [
    path('', include(router.urls)),
]
