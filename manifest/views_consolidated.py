"""
Consolidated manifest views with redundancies removed.
This replaces the original views.py with a cleaner, more maintainable structure.
"""

import os
import logging
import pandas as pd
from io import BytesIO, StringIO

from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.utils.encoding import smart_str
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.core.files.base import ContentFile
from django.utils import timezone

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

from .models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping, ManifestGroup
from products.models import ProductFamily
from .serializers import (
    ManifestSerializer, ManifestDetailSerializer, ManifestItemSerializer,
    ManifestGroupSerializer, ManifestTemplateSerializer, ManifestColumnMappingSerializer,
    ManifestUploadSerializer, ManifestMappingSerializer, ManifestGroupingSerializer,
    ManifestBatchSerializer
)

logger = logging.getLogger(__name__)


class ManifestViewSet(viewsets.ModelViewSet):
    """
    Main API endpoint for managing manifests.
    
    Provides CRUD operations for manifests as well as specialized actions 
    for uploading, mapping columns, grouping items, and creating batches.
    """
    queryset = Manifest.objects.all().order_by('-uploaded_at')
    # permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Return the appropriate serializer based on the action"""
        if self.action == 'retrieve':
            return ManifestDetailSerializer
        elif self.action == 'upload':
            return ManifestUploadSerializer
        elif self.action == 'apply_mapping':
            return ManifestMappingSerializer
        elif self.action == 'reopen_mapping':
            return serializers.Serializer
        elif self.action == 'group_items':
            return ManifestGroupingSerializer
        elif self.action == 'create_batch':
            return ManifestBatchSerializer
        return ManifestSerializer
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """Upload and process a new manifest file."""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                from .services import ManifestUploadService, ManifestParserService
                
                file_obj = serializer.validated_data['file']
                name = serializer.validated_data['name']
                reference = serializer.validated_data.get('reference')
                notes = serializer.validated_data.get('notes')
                user = request.user
                
                manifest = ManifestUploadService.process_upload(
                    file_obj=file_obj,
                    name=name,
                    user=user,
                    reference=reference,
                    notes=notes
                )
                
                ManifestParserService.parse_manifest(manifest_id=manifest.id)
                
                return Response(
                    ManifestDetailSerializer(manifest).data,
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as e:
                logger.exception("Error processing manifest upload")
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def preview(self, request):
        """
        Upload and preview a manifest file without saving to database.
        Combines functionality from ProcessManifestAPIView.
        """
        serializer = ManifestUploadSerializer(data=request.data)
        if serializer.is_valid():
            uploaded_file = serializer.validated_data['file']
            file_path = default_storage.save(uploaded_file.name, uploaded_file)
            
            try:
                from .services import ManifestParserService
                
                # Process the file content
                if uploaded_file.name.endswith('.csv'):
                    file_content = default_storage.open(file_path, 'rb').read()
                    parsed_data = ManifestParserService.parse_csv_content(file_content)
                else:
                    file_content = default_storage.open(file_path, 'rb').read()
                    parsed_data = ManifestParserService.parse_excel_content(file_content)
                
                headers = list(parsed_data[0].keys()) if parsed_data else []
                
                # Clean up the uploaded file
                default_storage.delete(file_path)
                
                return Response({
                    'status': 'success',
                    'message': 'Manifest file processed successfully.',
                    'data': parsed_data[:10],  # First 10 rows for preview
                    'headers': headers,
                    'total_rows': len(parsed_data)
                })
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}", exc_info=True)
                default_storage.delete(file_path)
                return Response({
                    'status': 'error',
                    'message': f'Error processing file: {str(e)}',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({
                'status': 'error',
                'message': 'Invalid file upload.',
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def apply_mapping(self, request, pk=None):
        """Apply column mapping to a manifest."""
        manifest = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                from .services import ManifestMappingService
                
                logger.info(f"Mapping request received for manifest {pk}: {request.data}")
                
                template_id = serializer.validated_data.get('template_id')
                
                if template_id:
                    try:
                        from .models import ManifestTemplate
                        template = ManifestTemplate.objects.get(id=template_id)
                        manifest.template = template
                        manifest.save(update_fields=['template'])
                        logger.info(f"Associated template {template_id} with manifest {pk}")
                    except Exception as e:
                        logger.warning(f"Could not associate template {template_id} with manifest {pk}: {str(e)}")
                
                column_mapping = serializer.validated_data.get('column_mapping', {})
                column_mappings = serializer.validated_data.get('column_mappings', {})
                unmapped_columns = serializer.validated_data.get('unmapped_columns', {})
                
                final_mappings = column_mappings if column_mappings else column_mapping
                
                if template_id:
                    template_mappings = ManifestMappingService.get_template_mappings(template_id)
                    if unmapped_columns and isinstance(unmapped_columns, dict):
                        template_mappings.update(unmapped_columns)
                    final_mappings = template_mappings
                
                if final_mappings is None:
                    final_mappings = {}
                    
                if not isinstance(final_mappings, dict):
                    try:
                        if hasattr(final_mappings, 'items'):
                            final_mappings = dict(final_mappings)
                        elif isinstance(final_mappings, str):
                            import json
                            final_mappings = json.loads(final_mappings)
                        else:
                            final_mappings = {}
                    except Exception as e:
                        logger.error(f"Error converting mappings to dict: {str(e)}")
                        final_mappings = {}
                
                if not final_mappings:
                    return Response(
                        {'error': 'No column mappings provided. Please provide mappings or select a valid template.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                result = ManifestMappingService.apply_mapping(
                    manifest=manifest,
                    column_mappings=final_mappings
                )
                
                return Response({
                    'success': True,
                    'mapped_count': result.get('mapped_count', 0)
                })
            except Exception as e:
                logger.error(f"Error in apply_mapping: {str(e)}", exc_info=True)
                return Response(
                    {'error': f'Failed to apply mapping: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            logger.error(f"Serializer errors in apply_mapping: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reopen_mapping(self, request, pk=None):
        """Reopen column mapping for a manifest."""
        manifest = self.get_object()
        
        try:
            manifest.status = 'mapping'
            manifest.save(update_fields=['status'])
            
            return Response({
                'success': True,
                'message': 'Column mapping reopened'
            })
        except Exception as e:
            logger.error(f"Error in reopen_mapping: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to reopen mapping: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def group_items(self, request, pk=None):
        """Group similar items in a manifest."""
        manifest = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                from .services import ManifestGroupingService
                
                group_fields = serializer.validated_data.get('group_fields')
                
                result = ManifestGroupingService.group_items(
                    manifest_id=manifest.id,
                    group_fields=group_fields
                )
                
                return Response({
                    'success': True,
                    'group_count': result.get('data', {}).get('group_count', 0)
                })
            except Exception as e:
                logger.error(f"Error grouping items: {str(e)}", exc_info=True)
                return Response(
                    {'error': f'Failed to group items: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def create_batch(self, request, pk=None):
        """Create a receipt batch from a manifest."""
        manifest = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                from .services import ManifestBatchService
                
                location_id = serializer.validated_data['location_id']
                reference = serializer.validated_data.get('reference')
                notes = serializer.validated_data.get('notes')
                user = request.user
                
                result = ManifestBatchService.create_batch(
                    manifest=manifest,
                    location_id=location_id,
                    reference=reference,
                    notes=notes,
                    user=user
                )
                
                return Response({
                    'success': True,
                    'batch_id': result.get('batch_id'),
                    'message': result.get('message', 'Batch created successfully')
                })
            except Exception as e:
                logger.error(f"Error in create_batch: {str(e)}", exc_info=True)
                return Response(
                    {'error': f'Failed to create batch: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def suggested_mappings(self, request, pk=None):
        """Get suggested column mappings for this manifest."""
        manifest = self.get_object()
        
        try:
            from .services import ManifestMappingSuggestionService
            
            result = ManifestMappingSuggestionService.suggest_mappings(manifest=manifest)
            
            if result.get('success'):
                return Response(result)
            else:
                return Response(
                    {'error': result.get('error', 'Failed to generate suggested mappings')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except Exception as e:
            logger.error(f"Error in suggested_mappings: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to generate suggested mappings: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def system_fields(self, request):
        """Get available system fields for column mapping."""
        from .constants import SYSTEM_FIELDS, FIELD_GROUPS
        
        try:
            return Response({
                'success': True,
                'data': {
                    'fields': SYSTEM_FIELDS,
                    'groups': FIELD_GROUPS
                }
            })
        except Exception as e:
            logger.error(f"Error getting system fields: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to get system fields: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def link_to_batch(self, request, pk=None):
        """Link a manifest to a batch."""
        manifest = self.get_object()
        batch_id = request.data.get('batch_id')
        
        if not batch_id:
            return Response(
                {'error': 'batch_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from receiving.models import Batch
            
            batch = get_object_or_404(Batch, id=batch_id)
            manifest.receipt_batch = batch
            manifest.save(update_fields=['receipt_batch'])
            
            serializer = self.get_serializer(manifest)
            return Response({
                'success': True,
                'message': f'Manifest #{manifest.id} linked to batch #{batch.id} successfully',
                'manifest': serializer.data,
                'batch_id': batch.id
            })
        except Exception as e:
            logger.error(f"Error linking manifest to batch: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to link manifest to batch: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def batch(self, request, pk=None):
        """Get the batch linked to this manifest."""
        manifest = self.get_object()
        
        if not manifest.receipt_batch:
            return Response(
                {'error': 'No batch linked to this manifest'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from receiving.serializers import BatchSerializer
        
        serializer = BatchSerializer(manifest.receipt_batch)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download the original manifest file.
        Consolidates DownloadManifestAPIView functionality.
        """
        manifest = self.get_object()
        
        if not manifest.file:
            return Response({
                'error': 'No file associated with this manifest.',
            }, status=status.HTTP_404_NOT_FOUND)

        file_path = manifest.file.name
        
        if not default_storage.exists(file_path):
            return Response({
                'error': 'File not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            file = default_storage.open(file_path, 'rb')
            file_name = os.path.basename(file_path)
            return FileResponse(file, as_attachment=True, filename=file_name)
        except Exception as e:
            logger.error(f"Error serving file: {str(e)}", exc_info=True)
            return Response({
                'error': f'Error serving file: {str(e)}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """
        Export a remapped manifest with enhanced formatting.
        Consolidates DownloadRemappedManifestView functionality.
        """
        manifest = self.get_object()
        format = request.query_params.get('format', 'xlsx').lower()
        
        if format not in ['xlsx', 'csv']:
            return Response(
                {'error': 'Unsupported format. Use xlsx or csv.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        items = ManifestItem.objects.filter(manifest=manifest)
        
        if not items.exists():
            logger.warning(f"No items found for manifest ID: {pk}")
            return Response(
                {'error': 'No items found in this manifest.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            from .services.export_service import ManifestExportService
            return ManifestExportService.export_remapped_manifest(manifest, items, format)
        except Exception as e:
            logger.error(f"Export service error: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to generate export: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ManifestItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing manifest items.
    
    Provides read-only access to individual items from a manifest.
    """
    queryset = ManifestItem.objects.all()
    serializer_class = ManifestItemSerializer
    # permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on request parameters"""
        queryset = ManifestItem.objects.all()
        manifest_id = self.request.query_params.get('manifest', None)
        
        if manifest_id is not None:
            queryset = queryset.filter(manifest_id=manifest_id)
            
        status_filter = self.request.query_params.get('status', None)
        if status_filter is not None:
            queryset = queryset.filter(status=status_filter)
            
        return queryset


class ManifestGroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifest groups.
    
    Provides CRUD operations for manifest groups and product family mappings.
    Incorporates simplified family mapping from minimal_views.py.
    """
    queryset = ManifestGroup.objects.all()
    serializer_class = ManifestGroupSerializer
    # permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on request parameters"""
        queryset = ManifestGroup.objects.all()
        manifest_id = self.request.query_params.get('manifest', None)
        
        if manifest_id is not None:
            queryset = queryset.filter(manifest_id=manifest_id)
            
        return queryset
    
    @action(detail=True, methods=['post'])
    def set_product_family(self, request, pk=None):
        """
        Set the product family for a manifest group.
        Maintains backward compatibility while using simplified model.
        """
        group = self.get_object()
        family_id = request.data.get('family_id')
        
        if not family_id:
            return Response({'error': 'family_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product_family = ProductFamily.objects.get(id=family_id)
            group.product_family = product_family
            group.save(update_fields=['product_family'])
            
            serializer = self.get_serializer(group)
            return Response(serializer.data)
            
        except ProductFamily.DoesNotExist:
            return Response({'error': 'Product family not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def add_family(self, request, pk=None):
        """
        Associate a product family with a manifest group.
        Simplified version that uses the direct foreign key relationship.
        """
        group = self.get_object()
        family_id = request.data.get('family_id')
        is_primary = request.data.get('is_primary', False)
        notes = request.data.get('notes', '')
        
        if not family_id:
            return Response({'error': 'family_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product_family = ProductFamily.objects.get(id=family_id)
        except ProductFamily.DoesNotExist:
            return Response({'error': 'Product family not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Set as product family if specified or if no existing family
        if is_primary or not group.product_family:
            group.product_family = product_family
            group.save(update_fields=['product_family', 'family_mapping_updated_at'])
        
        # Return backward-compatible response
        response_data = {
            'id': f"{group.id}_{family_id}",
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
        """Remove a product family from a manifest group."""
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
        Returns backward-compatible format.
        """
        group = self.get_object()
        
        # In the simplified model, we only have one product family
        if not group.product_family:
            return Response([])
            
        # Return backward-compatible response
        response_data = [{
            'id': f"{group.id}_{group.product_family.id}",
            'manifest_group': group.id,
            'product_family': group.product_family.id,
            'product_family_name': group.product_family.name,
            'is_primary': True,
            'created_at': group.family_mapping_updated_at.isoformat() if group.family_mapping_updated_at else timezone.now().isoformat(),
            'updated_at': group.family_mapping_updated_at.isoformat() if group.family_mapping_updated_at else timezone.now().isoformat(),
            'notes': None
        }]
        
        return Response(response_data)


class ManifestTemplateViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifest templates.
    
    Provides CRUD operations for templates that define column mappings.
    """
    queryset = ManifestTemplate.objects.all()
    serializer_class = ManifestTemplateSerializer
    # permission_classes = [IsAuthenticated]


class ManifestColumnMappingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifest column mappings.
    
    Provides CRUD operations for individual column mappings within templates.
    """
    queryset = ManifestColumnMapping.objects.all()
    serializer_class = ManifestColumnMappingSerializer
    # permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on request parameters"""
        queryset = ManifestColumnMapping.objects.all()
        template_id = self.request.query_params.get('template', None)
        
        if template_id is not None:
            queryset = queryset.filter(template_id=template_id)
            
        return queryset


# REMOVED REDUNDANT VIEWS:
# - ProcessManifestAPIView (functionality moved to ManifestViewSet.preview action)
# - DownloadManifestAPIView (functionality moved to ManifestViewSet.download action) 
# - TestDownloadView (no longer needed)
# - DownloadRemappedManifestView (functionality moved to ManifestViewSet.export action)

# CONSOLIDATED FUNCTIONALITY:
# - File upload preview is now an action on ManifestViewSet
# - File downloads are now actions on ManifestViewSet
# - Export functionality is now an action on ManifestViewSet
# - Simplified ManifestGroupViewSet with direct product family relationship
# - Removed separate family mapping models and views for simpler architecture
