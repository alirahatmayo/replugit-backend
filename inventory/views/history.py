from rest_framework import viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..models import InventoryHistory
from ..serializers import InventoryHistorySerializer

class InventoryHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for viewing inventory history.
    """
    queryset = InventoryHistory.objects.select_related(
        'inventory', 'inventory__product', 'inventory__location', 'adjusted_by'
    ).all()
    serializer_class = InventoryHistorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['inventory', 'reason']
    search_fields = ['reference', 'notes']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']