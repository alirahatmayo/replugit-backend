# receiving/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'receiving'

# Create a router and register our viewset with it
router = DefaultRouter()
router.register(r'batches', views.ReceiptBatchViewSet, basename='batch')
router.register(r'items', views.BatchItemViewSet, basename='item')


# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
]