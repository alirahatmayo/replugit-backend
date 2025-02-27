from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from .models import Customer, CustomerChangeLog
from .serializers import CustomerSerializer, CustomerChangeLogSerializer
from django.db import models


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing customers.
    Supports filtering, searching, updates, and custom actions.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source_platform', 'is_active', 'created_at']
    search_fields = ['name', 'email', 'phone_number']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Search customers by name, phone number, or email.
        """
        query = request.query_params.get('q', '')
        customers = Customer.objects.filter(
            models.Q(name__icontains=query) |
            models.Q(email__icontains=query) |
            models.Q(phone_number__icontains=query)
        )
        serializer = self.get_serializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='activate')
    def activate(self, request, pk=None):
        """
        Reactivate a deactivated customer.
        """
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = True
        customer.save()
        return Response({'status': 'Customer reactivated successfully'})

    @action(detail=True, methods=['get'], url_path='changelog')
    def changelog(self, request, pk=None):
        """
        View the change log for a specific customer.
        """
        customer = get_object_or_404(Customer, pk=pk)
        changelog = CustomerChangeLog.objects.filter(customer=customer)
        serializer = CustomerChangeLogSerializer(changelog, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: deactivate instead of permanent delete.
        """
        customer = self.get_object()
        customer.is_active = False
        customer.save()
        return Response({'status': 'Customer deactivated successfully'}, status=status.HTTP_204_NO_CONTENT)

class CustomerChangeLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for CustomerChangeLogs.
    Provides filtering and searching capabilities for change logs.
    """
    queryset = CustomerChangeLog.objects.select_related('customer').all()
    serializer_class = CustomerChangeLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['field_name', 'updated_at']
    search_fields = ['customer__name', 'field_name', 'old_value', 'new_value']
    ordering_fields = ['updated_at']
    ordering = ['-updated_at']