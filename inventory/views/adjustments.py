import logging
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..models import InventoryAdjustment
from ..serializers import InventoryAdjustmentSerializer
from ..utils import success_response, error_response

logger = logging.getLogger(__name__)

class InventoryAdjustmentViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing inventory adjustments.
    """
    queryset = InventoryAdjustment.objects.select_related(
        'inventory', 'inventory__product', 'inventory__location',
        'created_by', 'approved_by'
    ).all()
    serializer_class = InventoryAdjustmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'reason', 'created_by', 'inventory__product']
    search_fields = ['reference', 'notes']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        """Set created_by when creating a new adjustment"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an adjustment"""
        adjustment = self.get_object()
        
        # Only pending adjustments can be approved
        if adjustment.status != 'PENDING':
            return error_response(
                f"Cannot approve adjustment with status {adjustment.status}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            with transaction.atomic():
                success = adjustment.approve(request.user)
                
                if success:
                    return success_response(
                        InventoryAdjustmentSerializer(adjustment).data,
                        message="Adjustment approved successfully"
                    )
                else:
                    return error_response(
                        "Failed to approve adjustment",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            logger.error(f"Error approving adjustment: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an adjustment"""
        adjustment = self.get_object()
        
        # Only pending adjustments can be rejected
        if adjustment.status != 'PENDING':
            return error_response(
                f"Cannot reject adjustment with status {adjustment.status}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
        reason = request.data.get('reason', '')
        
        try:
            with transaction.atomic():
                success = adjustment.reject(request.user, reason)
                
                if success:
                    return success_response(
                        InventoryAdjustmentSerializer(adjustment).data,
                        message="Adjustment rejected successfully"
                    )
                else:
                    return error_response(
                        "Failed to reject adjustment",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        except Exception as e:
            logger.error(f"Error rejecting adjustment: {str(e)}", exc_info=True)
            return error_response(
                str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )