# Import standard library modules
import os
import logging
import pandas as pd
from io import BytesIO, StringIO

# Import Django modules
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.utils.encoding import smart_str
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.core.files.base import ContentFile
from django.utils import timezone

# Import DRF modules
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

# Import from app
from .models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping, ManifestGroup
from .serializers import (
    ManifestSerializer, ManifestDetailSerializer, ManifestItemSerializer,
    ManifestGroupSerializer, ManifestTemplateSerializer, ManifestColumnMappingSerializer,
    ManifestUploadSerializer, ManifestMappingSerializer, ManifestGroupingSerializer,
    ManifestBatchSerializer
)

# Import services
from .services.export_service import ManifestExportService

# Set up logger for this module
logger = logging.getLogger(__name__)


class ManifestViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifests.
    
    Provides CRUD operations for manifests as well as specialized actions 
    for uploading, mapping columns, grouping items, and creating batches.
    """
    queryset = Manifest.objects.all().order_by('-uploaded_at')
    # Comment the permission class during development, but uncomment in production
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
        """
        Upload a new manifest file.
        
        Validates and processes the uploaded file, creating a manifest record
        and parsing the file contents into individual manifest items.
        """
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Use the service class for processing uploads
                from .services import ManifestUploadService, ManifestParserService
                
                file_obj = serializer.validated_data['file']
                name = serializer.validated_data['name']
                reference = serializer.validated_data.get('reference')
                notes = serializer.validated_data.get('notes')
                user = request.user
                
                # Delegate to service for processing upload
                manifest = ManifestUploadService.process_upload(
                    file_obj=file_obj,
                    name=name,
                    user=user,
                    reference=reference,
                    notes=notes
                )
                
                # Parse manifest in a background task or immediately depending on size
                # For simplicity, calling directly here, but could be moved to a task queue
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
    
    @action(detail=True, methods=['post'])
    def apply_mapping(self, request, pk=None):
        """
        Apply column mapping to a manifest.
        
        Maps source columns to target fields based on provided mapping or template.
        This enables the system to understand how to interpret the manifest data.
        """
        manifest = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Import the service
                from .services import ManifestMappingService
                
                # Log the received request data to help debug
                logger.info(f"Mapping request received for manifest {pk}: {request.data}")
                
                # Get data from serializer
                template_id = serializer.validated_data.get('template_id')
                
                # If using a template, save the reference to the manifest
                if template_id:
                    try:
                        from .models import ManifestTemplate
                        template = ManifestTemplate.objects.get(id=template_id)
                        manifest.template = template
                        manifest.save(update_fields=['template'])
                        logger.info(f"Associated template {template_id} with manifest {pk}")
                    except Exception as e:
                        logger.warning(f"Could not associate template {template_id} with manifest {pk}: {str(e)}")
                
                # Handle both column_mapping and column_mappings parameter names
                column_mapping = serializer.validated_data.get('column_mapping', {})
                column_mappings = serializer.validated_data.get('column_mappings', {})
                unmapped_columns = serializer.validated_data.get('unmapped_columns', {})
                
                logger.info(f"Extracted column_mapping: {column_mapping}")
                logger.info(f"Extracted column_mappings: {column_mappings}")
                logger.info(f"Extracted unmapped_columns: {unmapped_columns}")
                
                # Use whichever parameter has data
                final_mappings = column_mappings if column_mappings else column_mapping
                
                # If we're using a template, get mappings from the template
                if template_id:
                    logger.info(f"Using template {template_id} for mappings")
                    template_mappings = ManifestMappingService.get_template_mappings(template_id)
                    
                    # If we have unmapped_columns, merge them with the template mappings
                    if unmapped_columns and isinstance(unmapped_columns, dict):
                        logger.info(f"Merging {len(unmapped_columns)} unmapped columns with template mappings")
                        template_mappings.update(unmapped_columns)
                    
                    # Use template mappings as the final mappings
                    final_mappings = template_mappings
                
                # Ensure final_mappings is a dictionary
                if final_mappings is None:
                    final_mappings = {}
                    
                # Convert to dict if necessary
                if not isinstance(final_mappings, dict):
                    try:
                        # Try to convert to dictionary if possible
                        if hasattr(final_mappings, 'items'):
                            final_mappings = dict(final_mappings)
                        elif isinstance(final_mappings, str):
                            import json
                            final_mappings = json.loads(final_mappings)
                        else:
                            logger.warning(f"Could not convert column_mappings to dict, got type: {type(final_mappings)}")
                            final_mappings = {}
                    except Exception as e:
                        logger.error(f"Error converting mappings to dict: {str(e)}")
                        final_mappings = {}
                
                logger.info(f"Final mappings to apply: {final_mappings}")
                
                # Ensure we have something to map with
                if not final_mappings:
                    return Response(
                        {'error': 'No column mappings provided. Please provide mappings or select a valid template.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Delegate mapping to the service
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
            # Log serializer errors for debugging
            logger.error(f"Serializer errors in apply_mapping: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reopen_mapping(self, request, pk=None):
        """
        Reopen column mapping for a manifest.
        
        This allows users to modify column mappings even after they've been set and 
        the manifest has moved to later stages of processing.
        """
        manifest = self.get_object()
        
        try:
            # Reset the status to mapping
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
        """
        Group similar items in a manifest.
        
        Identifies and groups items with similar attributes (model, specs, etc.)
        to simplify inventory management and batch processing.
        """
        manifest = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Import the service
                from .services import ManifestGroupingService
                
                group_fields = serializer.validated_data.get('group_fields')
                
                # Pass manifest_id instead of manifest object
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
        """
        Create a receipt batch from a manifest.
        
        Converts the manifest data into a batch for receiving into inventory.
        Grouped items become batch items with quantities.
        """
        manifest = self.get_object()
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                # Import the CORRECT service that creates BatchItems from individual ManifestItems
                from .batch_service import ManifestBatchService
                
                location_id = serializer.validated_data['location_id']
                user = request.user
                
                # Use the correct service method that processes individual ManifestItems
                batch, validation_issues = ManifestBatchService.create_receipt_batch_from_manifest(
                    manifest=manifest,
                    location_id=location_id,
                    user_id=user.id if user else None
                )
                
                # Format the result to match expected response structure
                result = {
                    'batch_id': batch.id,
                    'batch_code': batch.batch_code,
                    'validation_issues': validation_issues,
                    'message': f'Batch created successfully with {batch.items.count()} individual items'
                }
                
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
        """
        Get suggested column mappings for this manifest based on column names.
        
        Analyzes column names in the manifest file and suggests appropriate
        field mappings based on common patterns and naming conventions.
        """
        manifest = self.get_object()
        
        try:
            # Import the service
            from .services import ManifestMappingSuggestionService
            
            # Get mapping suggestions from the service
            result = ManifestMappingSuggestionService.suggest_mappings(manifest=manifest)
            
            # Format the response to ensure consistent structure
            if result.get('success'):
                # If the suggestions are nested in data.suggestions, keep the structure intact
                return Response(result)
            else:
                # Return the error in a standard format
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
        """
        Get available system fields for column mapping.
        
        Returns a structured list of field definitions with metadata like
        data types, groups, and required status.
        """
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
        """
        Link a manifest to a batch.
        Requires batch_id in the request data.
        """
        manifest = self.get_object()
        batch_id = request.data.get('batch_id')
        
        if not batch_id:
            return Response(
                {'error': 'batch_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Import the Batch model from receiving app
            from receiving.models import Batch
            
            # Get the batch
            batch = get_object_or_404(Batch, id=batch_id)
            
            # Link the manifest to the batch
            manifest.batch = batch
            manifest.save()
            
            # Return success response with manifest and batch details
            serializer = self.get_serializer(manifest)
            return Response({
                'success': True,
                'message': f'Manifest #{manifest.id} linked to batch #{batch.id} successfully',
                'manifest': serializer.data,
                'batch_id': batch.id
            })
        except Batch.DoesNotExist:
            return Response(
                {'error': f'Batch with id {batch_id} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error linking manifest to batch: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to link manifest to batch: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def batch(self, request, pk=None):
        """
        Get the batch linked to this manifest
        """
        manifest = self.get_object()
        
        if not hasattr(manifest, 'batch') or not manifest.batch:
            return Response(
                {'error': 'No batch linked to this manifest'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Import the serializer here to avoid circular imports
        from receiving.serializers import BatchSerializer
        
        serializer = BatchSerializer(manifest.batch)
        return Response(serializer.data)


class ManifestItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing manifest items.
    
    Provides read-only access to individual items from a manifest.
    Items can be filtered by manifest ID and status.
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
    API endpoint for viewing and updating manifest groups.
    
    Provides read access to groups of similar items from a manifest,
    and allows updating the product_family field for family mapping.
    Groups can be filtered by manifest ID.
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
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        For now, only allow updates to specific fields.
        """
        if self.action in ['partial_update', 'update']:
            # Allow updates but only to specific fields
            return super().get_permissions()
        return super().get_permissions()
    
    def partial_update(self, request, *args, **kwargs):
        """
        Allow partial updates but only for specific fields like product_family.
        """
        instance = self.get_object()
        
        # Only allow updating product_family field for family mapping
        allowed_fields = ['product_family']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        if not update_data:
            return Response(
                {'error': 'Only product_family field can be updated'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=update_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
  
class ManifestTemplateViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifest templates.
    
    Provides CRUD operations for templates that define column mappings.
    Templates can be reused across multiple manifests.
    """
    queryset = ManifestTemplate.objects.all()
    serializer_class = ManifestTemplateSerializer
    # permission_classes = [IsAuthenticated]


class ManifestColumnMappingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing manifest column mappings.
    
    Provides CRUD operations for individual column mappings within templates.
    Mappings can be filtered by template ID.
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


class ProcessManifestAPIView(APIView):
    """
    API view for uploading and processing manifest files.
    
    Handles the initial upload and parsing of manifest files without
    creating permanent manifest records. Useful for previewing data
    before committing to the database.
    """
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = ManifestUploadSerializer

    def post(self, request, *args, **kwargs):
        """
        Handles the manifest file upload and data processing.
        
        Returns a preview of the parsed data along with headers.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            uploaded_file = serializer.validated_data['file']
            file_path = default_storage.save(uploaded_file.name, uploaded_file)
            file_url = default_storage.url(file_path)  # Get the URL
            try:
                # Create a temporary manifest instance for preview
                from .models import Manifest
                from .services import ManifestParserService, ManifestPreviewService
                
                # Create a temporary manifest that won't be saved to DB
                temp_manifest = Manifest(
                    name=f"preview_{uploaded_file.name}",
                    file=file_path,
                    status="preview"
                )
                
                # Process the file content using existing parser service
                if uploaded_file.name.endswith('.csv'):
                    file_content = default_storage.open(file_path, 'rb').read()
                    parsed_data = ManifestParserService.parse_csv_content(file_content)
                else:
                    file_content = default_storage.open(file_path, 'rb').read()
                    parsed_data = ManifestParserService.parse_excel_content(file_content)
                
                # Extract headers
                headers = list(parsed_data[0].keys()) if parsed_data else []
                
                # Clean up the uploaded file since we only need it for preview
                default_storage.delete(file_path)
                
                return Response({
                    'status': 'success',
                    'message': 'Manifest file uploaded and processed successfully.',
                    'data': parsed_data[:10],  # Only return the first 10 rows for preview
                    'headers': headers,
                    'file_url': file_url,
                    'total_rows': len(parsed_data)
                })
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}", exc_info=True)
                default_storage.delete(file_path)  # Clean up the uploaded file on error
                return Response({
                    'status': 'error',
                    'message': f'Error processing file: {str(e)}',
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Handle serializer validation errors
            return Response({
                'status': 'error',
                'message': 'Invalid file upload.',
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)


class DownloadManifestAPIView(APIView):
    """
    API view to download a manifest file from the server.
    
    Allows retrieving the original manifest file that was uploaded.
    """
    def get(self, request, *args, **kwargs):
        """
        Download the manifest file from the server based on file URL.
        
        Returns the file as an attachment for download.
        """
        file_url = request.GET.get('file_url')
        if not file_url:
            return Response({
                'status': 'error',
                'message': 'Missing file_url parameter.',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Remove the leading slash if present.
        if file_url.startswith('/'):
            file_path = file_url[1:]
        else:
            file_path = file_url

        # Construct the full file path using settings.MEDIA_ROOT
        full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)

        if not default_storage.exists(file_path):
            return Response({
                'status': 'error',
                'message': 'File not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            file = default_storage.open(file_path, 'rb')
            file_name = os.path.basename(full_file_path)
            return FileResponse(file, as_attachment=True, filename=file_name)
        except Exception as e:
            logger.error(f"Error serving file: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'message': f'Error serving file: {str(e)}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestDownloadView(APIView):
    """
    Test endpoint to diagnose download functionality issues.
    """
    def get(self, request, pk=None):
        try:
            # Log that we entered this view
            logger.info(f"TestDownloadView accessed for manifest ID: {pk}")
            
            # Try to get the manifest
            manifest = get_object_or_404(Manifest, pk=pk)
            logger.info(f"Found manifest in test view: {manifest.name} (ID: {manifest.id})")
            
            # Create a simple response with manifest details
            data = {
                'id': manifest.id,
                'name': manifest.name,
                'status': manifest.status,
                'items_count': ManifestItem.objects.filter(manifest=manifest).count(),
                'message': 'If you see this, URL routing to this manifest ID is working correctly.'
            }
            
            return Response(data)
            
        except Exception as e:
            logger.error(f"Error in TestDownloadView: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Test download view error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DownloadRemappedManifestView(APIView):
    """
    API view for downloading a remapped manifest with enhanced formatting and summaries.
    """
    def get(self, request, pk=None):
        try:
            # Debug logging
            logger.info(f"DownloadRemappedManifestView accessed for manifest ID: {pk}")
            
            # Try to get the manifest
            manifest = get_object_or_404(Manifest, pk=pk)
            logger.info(f"Found manifest: {manifest.name} (ID: {manifest.id})")
            
            format = request.query_params.get('format', 'xlsx').lower()
            logger.info(f"Requested format: {format}")
            
            if format not in ['xlsx', 'csv']:
                return Response(
                    {'error': 'Unsupported format. Use xlsx or csv.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the manifest items with their mapped fields
            items = ManifestItem.objects.filter(manifest=manifest)
            
            # If no items, return error
            if not items.exists():
                logger.warning(f"No items found for manifest ID: {pk}")
                return Response(
                    {'error': 'No items found in this manifest.'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            logger.info(f"Found {items.count()} items for manifest ID: {pk}")
            
            # Use the ManifestExportService to generate the export file
            try:
                # Delegate export functionality to the service
                return ManifestExportService.export_remapped_manifest(manifest, items, format)
            except Exception as e:
                logger.error(f"Export service error: {str(e)}", exc_info=True)
                return Response(
                    {'error': f'Failed to generate export: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Exception as e:
            logger.error(f"Error in DownloadRemappedManifestView: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to download manifest: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



