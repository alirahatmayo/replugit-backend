from rest_framework import viewsets
from rest_framework.filters import SearchFilter, OrderingFilter

from ..models import Location
from ..serializers import LocationSerializer

class LocationViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing inventory locations/warehouses.
    """
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code']