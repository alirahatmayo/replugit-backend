import pandas as pd
from io import BytesIO, StringIO
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from receiving.models import Batch
from receiving.serializers import BatchSerializer

@action(detail=True, methods=['get'])
def download_remapped(self, request, pk=None):
    """
    Download a manifest in remapped format (XLSX or CSV)
    with a hidden company signature embedded in the file.
    """
    manifest = self.get_object()
    format = request.query_params.get('format', 'xlsx').lower()
    
    if format not in ['xlsx', 'csv']:
        return Response(
            {'error': 'Unsupported format. Use xlsx or csv.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get the manifest items with their mapped fields
    items = ManifestItem.objects.filter(manifest=manifest)
    
    # If no items, return error
    if not items.exists():
        return Response(
            {'error': 'No items found in this manifest.'},
            status=status.HTTP_404_NOT_FOUND
        )
        
    # Create a DataFrame with the mapped data
    data = []
    for item in items:
        # Extract all mapped fields
        item_data = {
            'Serial Number': item.serial,
            'Manufacturer': item.manufacturer,
            'Model': item.model,
            'Processor': item.processor,
            'Memory': item.memory,
            'Storage': item.storage,
            'Battery Status': item.battery,
            'Condition Grade': item.condition_grade,
            'Condition Notes': item.condition_notes,
            'Barcode': item.barcode,
            'Price': item.unit_price
            # Add other fields as needed
        }
        data.append(item_data)
    
    df = pd.DataFrame(data)
    
    # Create a response with the right content type
    if format == 'xlsx':
        # Create BytesIO buffer to store Excel file
        buffer = BytesIO()
        
        # Create Excel writer
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Manifest')
            
            # Get the workbook and add hidden signature
            workbook = writer.book
            
            # Add hidden worksheet with company signature
            signature_sheet = workbook.create_sheet("_signature", 1)
            signature_sheet.sheet_state = 'hidden'
            
            # Add company signature information
            signature_sheet['A1'] = "REPLUGIT DATA EXPORT"
            signature_sheet['A2'] = f"Manifest ID: {manifest.id}"
            signature_sheet['A3'] = f"Export Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            signature_sheet['A4'] = f"User: {request.user.username if request.user.is_authenticated else 'Anonymous'}"
            signature_sheet['A5'] = "This file contains proprietary data from Replugit."
            
            # Add hidden custom document property
            workbook.properties.creator = "Replugit Data Export System"
            workbook.properties.title = f"Manifest {manifest.name} - Replugit Export"
            workbook.properties.description = f"Exported from Replugit on {timezone.now().strftime('%Y-%m-%d')}"
            workbook.properties.keywords = f"replugit,manifest,{manifest.id}"
        
        # Set response headers
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=manifest_{manifest.id}_remapped.xlsx'
    
    else:  # CSV format
        # Create CSV with a hidden signature line at the end
        buffer = StringIO()
        
        # Write data to CSV
        df.to_csv(buffer, index=False)
        
        # Add hidden signature as a comment line
        signature = f"# REPLUGIT DATA EXPORT - Manifest ID: {manifest.id} - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        buffer.write(f"\n{signature}")
        
        # Set response headers
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=manifest_{manifest.id}_remapped.csv'
    
    return response

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
    
    if not manifest.batch:
        return Response(
            {'error': 'No batch linked to this manifest'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    serializer = BatchSerializer(manifest.batch)
    return Response(serializer.data)