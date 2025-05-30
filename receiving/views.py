from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework import viewsets, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from .models import ReceiptBatch, BatchItem
from .serializers import (
    ReceiptBatchSerializer, 
    ReceiptBatchDetailSerializer,
    ReceiptBatchCreateSerializer,
    BatchItemSerializer,
    ReceiptItemCreateSerializer,
    BatchItemListSerializer,
    BatchSerializer,
    BatchItemDestinationSerializer
)
from inventory.models import InventoryReceipt, Location
# Fix the import to use the correct app name (singular)
from manifest.models import Manifest
from manifest.serializers import ManifestSerializer
import logging

logger = logging.getLogger(__name__)


class ReceiptBatchViewSet(viewsets.ModelViewSet):
    """API endpoint for receipt batches"""
    queryset = ReceiptBatch.objects.all().order_by('-receipt_date')
    serializer_class = ReceiptBatchSerializer
    # permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return ReceiptBatchCreateSerializer
        elif self.action in ['retrieve', 'process']:
            return ReceiptBatchDetailSerializer
        elif self.action == 'update_batch_destinations':
            return BatchItemDestinationSerializer
        return ReceiptBatchSerializer
    
    def get_queryset(self):
        """Filter batches based on query parameters"""
        queryset = super().get_queryset()
        
        # Handle common filters
        filters = {}
        
        # Location filter
        location_id = self.request.query_params.get('location')
        if location_id:
            filters['location_id'] = location_id
            
        # Status filter
        status_filter = self.request.query_params.get('status')
        if status_filter:
            filters['status'] = status_filter
            
        # Date range filters
        date_from = self.request.query_params.get('date_from')
        if date_from:
            filters['receipt_date__gte'] = date_from
            
        date_to = self.request.query_params.get('date_to')
        if date_to:
            filters['receipt_date__lte'] = date_to
            
        # Text search filters
        reference = self.request.query_params.get('reference')
        if reference:
            filters['reference__icontains'] = reference
            
        batch_code = self.request.query_params.get('batch_code')
        if batch_code:
            filters['batch_code__icontains'] = batch_code
            
        return queryset.filter(**filters)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new receipt batch with items"""
        # Get and validate the serializer
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the batch
        batch = serializer.save()
        
        # Process immediately if requested
        process_immediately = request.data.get('process_immediately', False)
        if process_immediately:
            batch.process_batch()
            
        # Return detailed response
        return Response(
            ReceiptBatchDetailSerializer(batch).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def process(self, request, pk=None):
        """Process all unprocessed receipts in a batch"""
        batch = self.get_object()
        
        # Check if batch is already completed
        if batch.status == 'completed':
            return Response({
                "status": batch.status,
                "message": "Batch is already processed"
            })
            
        # Get count of unprocessed receipts
        unprocessed_count = batch.unprocessed_items.count()  # Using the new model property
        if unprocessed_count == 0:
            return Response({
                "status": batch.status,
                "message": "No unprocessed receipts found in batch"
            })
              # Process the batch
        try:
            # Use the enhanced model methods instead of direct service calls
            result = batch.process_batch()
            
            # Get updated counts
            total_receipts = batch.items.count()
            processed_receipts = batch.items.count() - batch.unprocessed_items.count()
                
            return Response({
                "status": batch.status,
                "message": f"Processed {processed_receipts} of {total_receipts} receipts",
                "processed_count": processed_receipts,
                "total_count": total_receipts
            })
        except Exception as e:
            from .error_handling import handle_batch_processing_error
            error_context = handle_batch_processing_error(batch, e)
            return Response(
                error_context,
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def add_items(self, request, pk=None):
        """Add items to a batch"""
        batch = self.get_object()
          # Use our validation helper
        try:
            from .validation import validate_batch_status_for_modification
            validate_batch_status_for_modification(batch)
        except serializers.ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate request data
        serializer = ReceiptItemCreateSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        items_added = 0
        items_updated = 0
        errors = []
        for item_data in serializer.validated_data:
            product_id = item_data.get('product')
            product_family_id = item_data.get('product_family')
            quantity = item_data.get('quantity')
            
            try:
                # Find product or product family
                if product_id:
                    from products.models import Product
                    product = Product.objects.get(pk=product_id)
                    product_family = None
                else:
                    from products.models import ProductFamily
                    product_family = ProductFamily.objects.get(pk=product_family_id)
                    product = None
                
                # Check if item already exists
                if product:
                    existing_item = batch.items.filter(product=product).first()
                else:
                    existing_item = batch.items.filter(product_family=product_family).first()
                    
                if existing_item:
                    # Update existing item
                    existing_item.quantity += quantity
                    
                    # Update other fields if provided
                    if 'unit_cost' in item_data and item_data['unit_cost'] is not None:
                        existing_item.unit_cost = item_data['unit_cost']
                    if 'notes' in item_data:
                        existing_item.notes = item_data['notes']
                    if 'requires_unit_qc' in item_data:
                        existing_item.requires_unit_qc = item_data['requires_unit_qc']
                    if 'create_product_units' in item_data:
                        existing_item.create_product_units = item_data['create_product_units']
                    if 'skip_inventory_receipt' in item_data:
                        existing_item.skip_inventory_receipt = item_data['skip_inventory_receipt']
                    
                    existing_item.save()
                    items_updated += 1
                else:                    # Create new item
                    new_item = BatchItem(
                        batch=batch,
                        product=product,
                        product_family=product_family,
                        quantity=quantity,
                        unit_cost=item_data.get('unit_cost'),
                        notes=item_data.get('notes', ''),
                        requires_unit_qc=item_data.get('requires_unit_qc', False),
                        create_product_units=item_data.get('create_product_units', True),
                        skip_inventory_receipt=item_data.get('skip_inventory_receipt', False)
                    )
                    new_item.save()
                    items_added += 1
                    
            except (Product.DoesNotExist, ProductFamily.DoesNotExist):
                errors.append(f"Product or product family with ID {product_id or product_family_id} not found")
            except Exception as e:
                errors.append(f"Error adding item: {str(e)}")
        
        # Recalculate batch totals
        batch.calculate_totals()
        
        # Process immediately if requested
        process_immediately = request.data.get('process_immediately', False)
        if process_immediately and (items_added > 0 or items_updated > 0):
            batch.process_batch()
        
        return Response({
            "success": True,
            "message": f"Added {items_added} items, updated {items_updated} items in batch",
            "batch_id": str(batch.id),
            "batch_code": batch.batch_code,
            "items_added": items_added,
            "items_updated": items_updated,
            "current_item_count": batch.items.count(),
            "status": batch.status,
            "errors": errors if errors else None
        })
    
    @action(detail=False, methods=['post'])
    def create_from_manifest(self, request):
        """Create a receipt batch from a manifest"""
        manifest_id = request.data.get('manifest_id')
        location_id = request.data.get('location_id')
        reference = request.data.get('reference')
        notes = request.data.get('notes')
        
        if not manifest_id:
            return Response(
                {"error": "manifest_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if not location_id:
            return Response(
                {"error": "location_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Use the manifest service to create a batch
            from manifest.services import ManifestBatchService
            batch = ManifestBatchService.create_receipt_batch(
                manifest_id=manifest_id,
                location_id=location_id,
                reference=reference,
                notes=notes,
                created_by=request.user
            )
              # Return the created batch details
            return Response(
                ReceiptBatchDetailSerializer(batch).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            from .error_handling import ReceivingError
            
            error_context = {
                "error": str(e),
                "manifest_id": manifest_id,
                "location_id": location_id
            }
            
            logger.exception(f"Error creating batch from manifest {manifest_id}: {str(e)}")
            return Response(
                error_context,
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def update_batch_destinations(self, request, pk=None):
        """
        Update the destination for all items in a batch at once
        
        This action allows setting the same destination for all items in a batch:
        - 'inventory': Direct to inventory (no QC needed)
        - 'qc': Send to Quality Control
        - 'pending': Decision pending
        
        Request should contain:
        - destination: The destination ('inventory', 'qc', or 'pending')
        - notes: Optional notes
        """
        batch = self.get_object()
        
        # Validate request data using the destination serializer
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        destination = serializer.validated_data['destination']
        notes = serializer.validated_data.get('notes', '')
        
        # Process all items in the batch
        from .services import ReceivingBatchService
        updated_items = []
        errors = []
        for item in batch.items.all():
            try:
                updated_item = ReceivingBatchService.update_batch_item_destination(
                    item, destination, notes
                )
                updated_items.append(updated_item.id)
            except Exception as e:
                from .error_handling import handle_item_processing_error
                error_context = handle_item_processing_error(item, e)
                errors.append(f"Error updating item {item.id}: {str(e)}")
        
        return Response({
            "success": True,
            "message": f"Updated destination for {len(updated_items)} items in batch {batch.batch_code}",
            "batch_id": str(batch.id),
            "batch_code": batch.batch_code,
            "updated_items": updated_items,
            "errors": errors if errors else None
        })


class BatchItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing batch items.
    
    This viewset provides CRUD operations for batch items, with optional
    filtering by batch ID. Also provides actions to update the destination
    (inventory or QC) for items.
    """
    serializer_class = BatchItemSerializer
    # permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'update_destination':
            return BatchItemDestinationSerializer
        elif self.action == 'list':
            return BatchItemListSerializer
        return BatchItemSerializer
        if self.action == 'list':
            return BatchItemListSerializer
        return BatchItemSerializer
    
    def get_queryset(self):
        """
        Filter batch items based on query parameters.
        Allows filtering by batch ID and product ID.
        """
        queryset = BatchItem.objects.all().select_related('product', 'inventory_receipt')
        
        # Filter by batch
        batch_id = self.request.query_params.get('batch')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
            
        # Filter by product
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
            
        return queryset
    
    def perform_create(self, serializer):
        """Create a new batch item"""
        batch_item = serializer.save()
        
        # Create inventory receipt if specified and not skipped
        if not batch_item.skip_inventory_receipt:
            batch = batch_item.batch
            
            from inventory.models import InventoryReceipt
            
            receipt_data = {
                'quantity': batch_item.quantity,
                'location': batch.location,
                'unit_cost': batch_item.unit_cost,
                'requires_unit_qc': batch_item.requires_unit_qc,
                'create_product_units': batch_item.create_product_units,
                'is_processed': False,
                'reference': batch.reference,
                'batch_code': batch.batch_code,
                'batch': batch,
                'created_by': self.request.user,
                'notes': batch_item.notes
            }
            
            # Add product or product_family based on what's available
            if batch_item.product:
                receipt_data['product'] = batch_item.product
            elif batch_item.product_family:
                receipt_data['product_family'] = batch_item.product_family
            
            inventory_receipt = InventoryReceipt.objects.create(**receipt_data)
            
            # Set the one-way relationship
            batch_item.inventory_receipt = inventory_receipt
            batch_item.save(update_fields=['inventory_receipt'])
            
            # Update batch totals
            batch.calculate_totals()
    
    @transaction.atomic
    def perform_update(self, serializer):
        """Update a batch item and its linked inventory receipt"""
        batch_item = serializer.instance
        updated_item = serializer.save()
        
        # Update linked inventory receipt if it exists and not skipped
        if updated_item.inventory_receipt and not updated_item.skip_inventory_receipt:
            receipt = updated_item.inventory_receipt
            receipt.quantity = updated_item.quantity
            receipt.unit_cost = updated_item.unit_cost
            receipt.requires_unit_qc = updated_item.requires_unit_qc
            receipt.create_product_units = updated_item.create_product_units
            receipt.notes = updated_item.notes
            receipt.save()
          # Update batch totals
        updated_item.batch.calculate_totals()
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Delete a batch item and its linked inventory receipt"""
        batch = instance.batch
        
        # Delete linked inventory receipt if it exists and not processed
        if instance.inventory_receipt and not instance.inventory_receipt.is_processed:
            instance.inventory_receipt.delete()
        
        # Delete the batch item
        instance.delete()
        
        # Update batch totals
        batch.calculate_totals()
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def update_destination(self, request, pk=None):
        """
        Update the destination of a batch item (inventory or QC)
        
        This action allows changing where received items should go:
        - 'inventory': Direct to inventory (no QC needed)
        - 'qc': Send to Quality Control
        - 'pending': Decision pending
        """
        batch_item = self.get_object()
        
        # Validate request data using the destination serializer
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        destination = serializer.validated_data['destination']
        notes = serializer.validated_data.get('notes', '')
        
        # Use service method to update destination
        from .services import ReceivingBatchService
        updated_item = ReceivingBatchService.update_batch_item_destination(
            batch_item, destination, notes
        )
        
        # Return updated item
        return Response(BatchItemSerializer(updated_item).data)
        
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def bulk_update_destination(self, request):
        """
        Bulk update the destination for multiple batch items
        
        Request should contain:
        - item_ids: List of batch item IDs
        - destination: The destination ('inventory', 'qc', or 'pending')
        - notes: Optional notes
        """
        item_ids = request.data.get('item_ids', [])
        destination = request.data.get('destination')
        notes = request.data.get('notes', '')
        
        if not item_ids:
            return Response(
                {"error": "item_ids is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if not destination:
            return Response(
                {"error": "destination is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Use our standardized validation
        try:
            from .validation import validate_destination
            validate_destination(destination)
        except serializers.ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process all items
        from .services import ReceivingBatchService
        updated_items = []
        errors = []
        
        for item_id in item_ids:
            try:
                batch_item = BatchItem.objects.get(pk=item_id)
                updated_item = ReceivingBatchService.update_batch_item_destination(
                    batch_item, destination, notes
                )
                updated_items.append(updated_item.id)
            except BatchItem.DoesNotExist:
                errors.append(f"Batch item with ID {item_id} not found")
            except Exception as e:
                from .error_handling import handle_item_processing_error
                try:
                    # If we have the batch item object, use it for detailed error handling
                    if 'batch_item' in locals() and batch_item:
                        error_info = handle_item_processing_error(batch_item, e)
                        logger.error(f"Error details: {error_info}")
                        errors.append(f"Error updating item {item_id}: {str(e)}")
                    else:
                        # Fallback if we don't have the item object
                        logger.error(f"Error updating batch item {item_id}: {str(e)}")
                        errors.append(f"Error updating item {item_id}: {str(e)}")
                except Exception:
                    # Ensure we don't crash during error handling
                    errors.append(f"Error updating item {item_id}: {str(e)}")
        
        return Response({
            "success": True,
            "message": f"Updated destination for {len(updated_items)} items",
            "updated_items": updated_items,
            "errors": errors if errors else None
        })


class BatchViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing batches.
    """
    serializer_class = BatchSerializer

    @action(detail=True, methods=['get'])
    def manifest(self, request, pk=None):
        """
        Get the manifest linked to this batch
        """
        batch = self.get_object()
        
        # Query for manifest that references this batch
        try:
            manifest = Manifest.objects.get(batch=batch)
            serializer = ManifestSerializer(manifest)
            return Response(serializer.data)
        except Manifest.DoesNotExist:
            return Response(
                {'error': 'No manifest found for this batch'},
                status=status.HTTP_404_NOT_FOUND
            )
