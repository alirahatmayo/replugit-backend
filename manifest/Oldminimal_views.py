from django.shortcuts import get_object_or_404
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (
    Manifest, 
    ManifestItem, 
    ManifestTemplate, 
    ManifestColumnMapping, 
    ManifestGroup
)
from products.models import ProductFamily
from .serializers import (
    ManifestSerializer, 
    ManifestDetailSerializer, 
    ManifestItemSerializer,
    ManifestGroupSerializer, 
    ManifestTemplateSerializer, 
    ManifestColumnMappingSerializer,
    ManifestUploadSerializer, 
    ManifestMappingSerializer, 
    ManifestGroupingSerializer,
    ManifestBatchSerializer, 
    ProductFamilyMappingSerializer
)

# Import the rest of your existing code but exclude ManifestGroupFamilyMapping references
# This is a placeholder - you should copy the contents from views.py.bak and remove references

class ManifestGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifest groups.
    
    Provides CRUD operations for manifest groups as well as specialized actions 
    for managing product family mappings.
    """
    queryset = ManifestGroup.objects.all()
    serializer_class = ManifestGroupSerializer
    
    def get_queryset(self):
        """Filter queryset based on request parameters"""
        queryset = ManifestGroup.objects.all()
        
        # Filter by manifest ID
        manifest_id = self.request.query_params.get('manifest', None)
        
        if manifest_id is not None:
            queryset = queryset.filter(manifest_id=manifest_id)
            
        return queryset
    @action(detail=True, methods=['post'])
    def add_family(self, request, pk=None):
        """
        Associate a product family with a manifest group.
        POST /api/manifests/groups/{id}/add_family/
        """
        group = self.get_object()
        family_id = request.data.get('family_id')
        is_primary = request.data.get('is_primary', False)
        notes = request.data.get('notes', '')
        
        if not family_id:
            return Response({'error': 'family_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the product family by ID without modifying it
            product_family = ProductFamily.objects.get(id=family_id)
        except ProductFamily.DoesNotExist:
            return Response({'error': 'Product family not found'}, status=status.HTTP_404_NOT_FOUND)
          # Set as product family if specified or if no existing family
        if is_primary or not group.product_family:
            group.product_family = product_family
            group.save(update_fields=['product_family', 'family_mapping_updated_at'])
        
        # Create a response that mimics the old format for backward compatibility
        response_data = {
            'id': f"{group.id}_{family_id}",  # Mimic the old composite ID
            'manifest_group': group.id,
            'product_family': family_id,
            'product_family_name': product_family.name,
            'is_primary': is_primary,
            'created_at': timezone.now().isoformat(),
            'updated_at': timezone.now().isoformat(),
            'notes': notes
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    @action(detail=True, methods=['post'])
    def remove_family(self, request, pk=None):
        """
        Remove a product family from a manifest group.
        POST /api/manifests/groups/{id}/remove_family/
        """
        group = self.get_object()
        family_id = request.data.get('family_id')
        
        if not family_id:
            return Response({'error': 'family_id is required'}, status=status.HTTP_400_BAD_REQUEST)
          # Check if we're removing the current family
        if group.product_family and group.product_family.id == int(family_id):
            group.product_family = None
            group.save(update_fields=['product_family', 'family_mapping_updated_at'])
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    @action(detail=True, methods=['get'])
    def family_mappings(self, request, pk=None):
        """
        Get all product family mappings for a manifest group.
        GET /api/manifests/groups/{id}/family_mappings/
        """
        group = self.get_object()
          # In the simplified model, we only have one product family
        if not group.product_family:
            return Response([])
            
        # Create a response that mimics the old format for backward compatibility
        response_data = [{
            'id': f"{group.id}_{group.product_family.id}",  # Mimic the old composite ID
            'manifest_group': group.id,
            'product_family': group.product_family.id,
            'product_family_name': group.product_family.name,
            'is_primary': True,
            'created_at': group.family_mapping_updated_at.isoformat(),
            'updated_at': group.family_mapping_updated_at.isoformat(),
            'notes': None  # We don't store per-family notes anymore
        }]
        
        return Response(response_data)

# Include other ViewSets and classes from your original views.py
# Important: Make sure to remove any references to ManifestGroupFamilyMapping
