import csv
import json
import pandas as pd
import hashlib
import os
from io import StringIO, BytesIO
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from django.http import FileResponse
from django.conf import settings
from .models import Manifest, ManifestItem, ManifestTemplate, ManifestColumnMapping, ManifestGroup
from .services.mapping_service import ManifestMappingService

class ManifestUploadService:
    """
    Service for handling manifest file uploads and processing.
    
    This service handles the parsing of uploaded manifest files,
    creation of Manifest objects, and processing of manifest items.
    """
    
    @classmethod
    def process_upload(cls, uploaded_file, name=None, manifest_type=None, source_type=None):
        """
        Process an uploaded manifest file.
        
        Args:
            uploaded_file: The uploaded file object
            name: Optional name for the manifest
            manifest_type: Optional manifest type
            source_type: Optional source type
            
        Returns:
            Manifest: The created Manifest object
        """
        from .models import Manifest
        import pandas as pd
        import json
        
        # Handle file based on its extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension == 'csv':
            # Process CSV file
            df = pd.read_csv(uploaded_file)
            items_data = df.to_dict(orient='records')
        elif file_extension in ['xls', 'xlsx']:
            # Process Excel file
            df = pd.read_excel(uploaded_file)
            items_data = df.to_dict(orient='records')
        elif file_extension == 'json':
            # Process JSON file
            items_data = json.load(uploaded_file)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        # Create manifest object
        manifest = Manifest.objects.create(
            name=name or uploaded_file.name,
            manifest_type=manifest_type,
            source_type=source_type,
            raw_file=uploaded_file
        )
        
        # Create manifest items
        manifest.create_items(items_data)
        
        return manifest

class ManifestParserService:
    """Service for parsing manifest files and creating manifest items"""
    
    @staticmethod
    def _clean_value_for_json(value):
        """
        Ensure a value is JSON serializable
        
        Args:
            value: Any value that needs to be stored in a JSONField
            
        Returns:
            A JSON serializable version of the value
        """
        if pd.isna(value) or value is None:
            return None
        elif isinstance(value, (int, float, bool, str)):
            return value
        else:
            # Convert any other types to string to ensure JSON serialization
            return str(value)
    
    @staticmethod
    def parse_manifest(manifest_id):
        """
        Parse a manifest file and create ManifestItem records
        
        Args:
            manifest_id: ID of the Manifest to parse
            
        Returns:
            List of created ManifestItem IDs
        """
        manifest = Manifest.objects.get(id=manifest_id)
        
        # Reset manifest status for parsing
        manifest.status = 'processing'
        manifest.save(update_fields=['status'])
        
        created_items = []
        
        try:
            if manifest.file_type == 'csv':
                with open(manifest.file.path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    
                    # Skip header if present
                    if manifest.has_header:
                        headers = next(reader)
                    else:
                        headers = [f"column_{i}" for i in range(50)]  # Generate column names
                    
                    # Process each row
                    for i, row in enumerate(reader, start=1):
                        # Create dictionary of row data with clean values
                        row_data = {
                            headers[j]: ManifestParserService._clean_value_for_json(value) 
                            for j, value in enumerate(row) if j < len(headers)
                        }
                        
                        # Create manifest item
                        item = ManifestItem.objects.create(
                            manifest=manifest,
                            row_number=i,
                            raw_data=row_data,
                        )
                        created_items.append(item.id)
            
            else:  # Excel file
                df = pd.read_excel(manifest.file.path)
                
                # Process each row
                for i, row in df.iterrows():
                    # Convert row to dictionary with clean values
                    row_dict = row.to_dict()
                    row_data = {
                        str(k): ManifestParserService._clean_value_for_json(v) 
                        for k, v in row_dict.items()
                    }
                    
                    # Create manifest item
                    item = ManifestItem.objects.create(
                        manifest=manifest,
                        row_number=i + 1,  # 1-based row numbers
                        raw_data=row_data,
                    )
                    created_items.append(item.id)
            
            # Update manifest status
            manifest.status = 'validation'
            manifest.save(update_fields=['status'])
            
            return created_items
            
        except Exception as e:
            manifest.status = 'failed'
            manifest.notes = f"Error parsing manifest: {str(e)}"
            manifest.save(update_fields=['status', 'notes'])
            raise

    @staticmethod
    def parse_csv_content(content):
        """
        Parse CSV content for preview
        
        Args:
            content: Raw CSV file content
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            # Decode content
            decoded = content.decode('utf-8-sig', errors='ignore')
            reader = csv.DictReader(StringIO(decoded))
            return list(reader)
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {str(e)}")
            
    @staticmethod
    def parse_excel_content(content):
        """
        Parse Excel content for preview
        
        Args:
            content: Raw Excel file content
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            df = pd.read_excel(BytesIO(content))
            return df.replace({pd.NA: None}).to_dict('records')
        except Exception as e:
            raise ValueError(f"Failed to parse Excel: {str(e)}")

class ManifestGroupingService:
    """Service for grouping similar manifest items"""
    
    @staticmethod
    def group_similar_items(manifest_id, group_fields=None):
        """
        Group similar items based on specified fields
        
        Args:
            manifest_id: ID of the manifest
            group_fields: List of fields to use for grouping (default: manufacturer, model, processor, memory, storage, condition_grade)
            
        Returns:
            Number of groups created
        """
        manifest = Manifest.objects.get(id=manifest_id)
        
        # Default grouping fields if none provided
        if not group_fields:
            group_fields = ['manufacturer', 'model', 'processor', 'memory', 'storage', 'condition_grade']
        
        # Clear existing groups for this manifest
        ManifestGroup.objects.filter(manifest=manifest).delete()
        
        # Get all mapped items
        items = ManifestItem.objects.filter(manifest=manifest, status='mapped')
        
        # Group items
        groups = {}
        
        for item in items:
            # Create a key from the specified fields
            key_parts = []
            for field in group_fields:
                key_parts.append(str(getattr(item, field, '') or ''))
            
            # Create group key hash
            group_key = hashlib.md5('|'.join(key_parts).encode()).hexdigest()
            
            # Add or update group
            if group_key in groups:
                groups[group_key]['quantity'] += 1
                groups[group_key]['items'].append(item)
                
                # Add price to total for averaging
                if item.unit_price:
                    groups[group_key]['price_total'] += item.unit_price
                    groups[group_key]['price_count'] += 1
                    
                # Collect condition notes
                if item.condition_notes and item.condition_notes not in groups[group_key]['notes_set']:
                    groups[group_key]['notes_set'].add(item.condition_notes)
            else:
                groups[group_key] = {
                    'quantity': 1,
                    'manufacturer': item.manufacturer,
                    'model': item.model,
                    'processor': item.processor,
                    'memory': item.memory,
                    'storage': item.storage,
                    'condition_grade': item.condition_grade,
                    'price_total': item.unit_price or 0,
                    'price_count': 1 if item.unit_price else 0,
                    'items': [item],
                    'notes_set': {item.condition_notes} if item.condition_notes else set()
                }
        
        # Create group objects
        with transaction.atomic():
            for group_key, group_data in groups.items():
                # Calculate average price
                avg_price = None
                if group_data['price_count'] > 0:
                    avg_price = group_data['price_total'] / group_data['price_count']
                
                # Combine notes
                notes = ', '.join(filter(None, group_data['notes_set']))
                
                # Create group
                group = ManifestGroup.objects.create(
                    manifest=manifest,
                    group_key=group_key,
                    quantity=group_data['quantity'],
                    manufacturer=group_data['manufacturer'],
                    model=group_data['model'],
                    processor=group_data['processor'],
                    memory=group_data['memory'],
                    storage=group_data['storage'],
                    condition_grade=group_data['condition_grade'],
                    unit_price=avg_price,
                    notes=notes
                )
                
                # Link items to group
                for item in group_data['items']:
                    item.group = group
                    item.save(update_fields=['group'])
        
        return len(groups)

class ManifestBatchService:
    """Service for creating receipt batches from manifests"""
    
    @staticmethod
    @transaction.atomic
    def create_receipt_batch(manifest_id, location_id, reference=None, notes=None, created_by=None):
        """
        Create a receipt batch from a manifest
        
        Args:
            manifest_id: ID of the manifest
            location_id: ID of the location for the batch
            reference: Optional reference for the batch
            notes: Optional notes for the batch
            created_by: User creating the batch
            
        Returns:
            Created ReceiptBatch instance
        """
        from receiving.models import ReceiptBatch, BatchItem
        
        manifest = Manifest.objects.get(id=manifest_id)
        
        # Create receipt batch
        batch = ReceiptBatch.objects.create(
            reference=reference or manifest.reference or f"Manifest {manifest.id}",
            location_id=location_id,
            notes=notes or manifest.notes,
            created_by=created_by or manifest.uploaded_by
        )
        
        # Link manifest to batch
        manifest.receipt_batch = batch
        manifest.status = 'processing'
        manifest.save(update_fields=['receipt_batch', 'status'])
        
        # Group manifest items if not already grouped
        if not manifest.groups.exists():
            ManifestGroupingService.group_similar_items(manifest.id)
            
        # Process each group as a batch item
        for group in manifest.groups.all():
            # Create batch item
            batch_item = BatchItem.objects.create(
                batch=batch,
                product_family=group.product_family,
                quantity=group.quantity,
                unit_cost=group.unit_price,
                notes=group.notes,
                requires_unit_qc=(group.condition_grade != 'A'),  # Require QC for non-A grade items
                source_type='manifest',
                source_id=str(manifest.id)
            )
            
            # Link group to batch item
            group.batch_item = batch_item
            group.save(update_fields=['batch_item'])
            
            # Link manifest items to batch item
            manifest.items.filter(group=group).update(
                batch_item=batch_item,
                status='processed',
                processed_at=timezone.now()
            )
        
        # Update manifest status
        manifest.status = 'completed'
        manifest.completed_at = timezone.now()
        manifest.save(update_fields=['status', 'completed_at'])
        
        # Calculate batch totals
        from receiving.services import ReceivingBatchService
        ReceivingBatchService.calculate_totals(batch)
        
        return batch

class ManifestMappingSuggestionService:
    """
    Service for generating mapping suggestions for manifest columns.
    
    This service analyzes manifest columns and suggests appropriate field mappings
    based on common patterns, column names, and previously used mappings.
    """
    
    # Common column name patterns and their suggested mappings
    COMMON_MAPPINGS = {
        # Model/product identifiers
        'model': ['model', 'model_number', 'model_no', 'model_name', 'model_id', 'modelnumber'],
        'manufacturer': ['manufacturer', 'brand', 'make', 'mfr', 'vendor', 'oem'],
        'product': ['product', 'product_name', 'item', 'item_name', 'product_id'],
        
        # Specifications
        'processor': ['processor', 'cpu', 'proc', 'processor_type', 'chip'],
        'memory': ['memory', 'ram', 'memory_size', 'memory_capacity', 'ram_size'],
        'storage': ['storage', 'hdd', 'ssd', 'drive', 'drive_size', 'storage_size', 'storage_capacity'],
        'screen_size': ['screen', 'screen_size', 'display', 'display_size', 'size'],
        
        # Condition
        'condition': ['condition', 'cond', 'grade', 'condition_grade'],
        'cosmetic_grade': ['cosmetic', 'cosmetic_grade', 'appearance', 'visual_grade'],
        'functional_grade': ['functional', 'functional_grade', 'working_condition'],
        
        # Identifiers
        'serial_number': ['serial', 'serial_number', 'serial_no', 'sn', 's/n', 'serialnumber'],
        'sku': ['sku', 'sku_number', 'stock_keeping_unit', 'item_number', 'item_code'],
        
        # Other common fields
        'quantity': ['quantity', 'qty', 'count', 'units', 'amount'],
        'price': ['price', 'unit_price', 'cost', 'msrp', 'value']
    }
    
    @classmethod
    def suggest_mappings(cls, manifest):
        """
        Generate suggested column mappings for a manifest.
        
        Args:
            manifest: The manifest to generate suggestions for
            
        Returns:
            dict: A dictionary containing suggested mappings for each column
        """
        if not manifest or not manifest.file:
            raise ValueError("Invalid manifest or missing file")
            
        # Get column names from the manifest
        columns = cls._get_manifest_columns(manifest)
        
        # Generate suggestions
        suggestions = {}
        for col in columns:
            # Convert column name to lowercase for matching
            col_lower = col.lower().strip()
            
            # Find matches in our common mappings
            for field, patterns in cls.COMMON_MAPPINGS.items():
                # Direct match with field name
                if col_lower == field:
                    suggestions[col] = field
                    break
                    
                # Check for match in patterns
                for pattern in patterns:
                    if pattern in col_lower or col_lower in pattern:
                        suggestions[col] = field
                        break
                        
                # Break the outer loop if we found a match
                if col in suggestions:
                    break
            
            # If no match found, leave it blank
            if col not in suggestions:
                suggestions[col] = ""
                
        return suggestions
    
    @classmethod
    def _get_manifest_columns(cls, manifest):
        """
        Extract column names from a manifest file.
        
        Args:
            manifest: The manifest to extract columns from
            
        Returns:
            list: A list of column names
        """
        if not default_storage.exists(manifest.file.name):
            raise FileNotFoundError(f"Manifest file not found: {manifest.file.name}")
            
        try:
            # Read first few rows to extract headers
            file_content = default_storage.open(manifest.file.name, 'rb').read()
            
            # Determine file type and parse accordingly
            if manifest.file.name.lower().endswith('.csv'):
                # Parse CSV
                file_io = StringIO(file_content.decode('utf-8', errors='ignore'))
                reader = csv.reader(file_io)
                headers = next(reader)  # Read first row as headers
            else:
                # Parse Excel
                df = pd.read_excel(BytesIO(file_content))
                headers = df.columns.tolist()
                
            return headers
                
        except Exception as e:
            raise RuntimeError(f"Error extracting columns: {str(e)}")

class ManifestExportService:
    """
    Service for exporting manifests in various formats.
    
    This service handles the formatting and generation of manifest exports,
    allowing manifests to be downloaded with enhanced formatting and summaries.
    """
    
    @classmethod
    def export_remapped_manifest(cls, manifest, items, format='xlsx'):
        """
        Export a manifest with remapped field values in the specified format.
        
        Args:
            manifest: The Manifest object to export
            items: QuerySet of ManifestItem objects to include
            format: Export format ('xlsx' or 'csv')
            
        Returns:
            FileResponse or HttpResponse containing the exported data
        """
        import pandas as pd
        import numpy as np
        from django.http import FileResponse, HttpResponse
        from io import BytesIO
        from django.utils import timezone
        
        # Create a list to hold all the data
        data = []
        
        # For each item, extract mapped_data and raw_data
        for item in items:
            # Start with mapped data
            row = item.mapped_data or {}
            
            # If there's raw data, include any fields not in mapped_data
            if item.raw_data:
                for key, value in item.raw_data.items():
                    if key not in row:
                        row[key] = value
            
            # Add manifest_item_id for reference
            row['manifest_item_id'] = item.id
            
            # Add to the data list
            data.append(row)
        
        # Create a dataframe
        df = pd.DataFrame(data)
        
        # Sort columns: mapped fields first, then original fields
        if not df.empty:
            # Get column names from first item's mapped_data
            mapped_cols = list(items.first().mapped_data.keys()) if items.first().mapped_data else []
            
            # Organize columns with mapped fields first
            ordered_cols = []
            for col in mapped_cols:
                if col in df.columns:
                    ordered_cols.append(col)
            
            # Add remaining columns
            for col in df.columns:
                if col not in ordered_cols:
                    ordered_cols.append(col)
            
            # Reorder the DataFrame columns
            df = df[ordered_cols]
        
        # Generate a timestamp for the filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{manifest.name}_{timestamp}"
        
        # Render to requested format
        if format.lower() == 'csv':
            # CSV format
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            
            df.to_csv(response, index=False)
            return response
        else:
            # XLSX format (default)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Manifest', index=False)
                
                # Get the xlsxwriter workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Manifest']
                
                # Add some formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#CCCCCC',
                    'border': 1
                })
                
                # Write the column headers with the header format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Auto-adjust column widths
                for i, col in enumerate(df.columns):
                    max_len = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    max_len = min(max_len + 2, 50)  # Add padding but cap width
                    worksheet.set_column(i, i, max_len)
            
            # Create the response with the Excel file
            output.seek(0)
            response = FileResponse(
                output, 
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
            return response

class ManifestPreviewService:
    """
    Service for handling manifest file previews and parsing without database persistence.
    Provides functionality to process uploaded manifest files and return preview data.
    """
    
    @staticmethod
    def generate_preview(file_path, file_name):
        """
        Generate a preview from an uploaded manifest file
        
        Args:
            file_path (str): Path to the temporarily stored file
            file_name (str): Original name of the uploaded file
            
        Returns:
            dict: Preview data containing parsed rows, headers, and metadata
        """
        try:
            from django.core.files.storage import default_storage
            
            # Process the file content using existing parser service
            if file_name.endswith('.csv'):
                file_content = default_storage.open(file_path, 'rb').read()
                parsed_data = ManifestParserService.parse_csv_content(file_content)
            else:
                file_content = default_storage.open(file_path, 'rb').read()
                parsed_data = ManifestParserService.parse_excel_content(file_content)
            
            # Extract headers
            headers = list(parsed_data[0].keys()) if parsed_data else []
            
            return {
                'status': 'success',
                'message': 'Manifest file processed successfully.',
                'data': parsed_data[:10],  # Only return first 10 rows for preview
                'headers': headers,
                'total_rows': len(parsed_data),
                'full_data': parsed_data  # Return all data for potential further processing
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing file in ManifestPreviewService: {str(e)}", exc_info=True)
            
            return {
                'status': 'error',
                'message': f'Error processing file: {str(e)}',
            }

class ManifestDownloadService:
    """
    Service for handling manifest file downloads.
    
    This service provides functionality to download original manifest files.
    """
    
    @classmethod
    def download_original_file(cls, file_url):
        """
        Download the original manifest file from storage.
        
        Args:
            file_url: The URL of the file to download
            
        Returns:
            FileResponse: A Django FileResponse for the requested file
        """
        # Remove the leading slash if present
        if file_url.startswith('/'):
            file_path = file_url[1:]
        else:
            file_path = file_url

        # Check if file exists
        if not default_storage.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Open the file from storage
            file = default_storage.open(file_path, 'rb')
            
            # Get the filename from the path
            file_name = os.path.basename(file_path)
            
            # Return as a file response for download
            return FileResponse(file, as_attachment=True, filename=file_name)
            
        except Exception as e:
            raise IOError(f"Error serving file: {str(e)}")
