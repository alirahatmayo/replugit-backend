from rest_framework import viewsets, filters, routers
from django_filters.rest_framework import DjangoFilterBackend
from django.urls import path, include
from .models import Product, ProductUnit
from .serializers import ProductSerializer, ProductUnitSerializer

class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Products.
    Supports filtering, searching, and ordering.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['platform', 'product_type', 'created_at']
    search_fields = ['name', 'sku', 'gtin']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    lookup_field = 'sku'


class ProductUnitViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ProductUnits.
    Supports filtering and searching by status and serial number.
    """
    queryset = ProductUnit.objects.select_related('product').all()
    serializer_class = ProductUnitSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_serialized', 'created_at']
    search_fields = ['serial_number', 'manufacturer_serial', 'product__name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']