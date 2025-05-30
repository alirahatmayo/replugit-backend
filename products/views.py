import logging
from rest_framework import viewsets, filters, status, routers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.urls import path, include
from django.core.exceptions import ValidationError

from .models import Product, ProductUnit, ProductFamily
from .serializers import ProductSerializer, ProductUnitSerializer, ProductFamilySerializer

logger = logging.getLogger(__name__)

class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Products.
    Supports filtering, searching, and ordering.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['platform', 'product_type', 'created_at']
    search_fields = ['name', 'sku', 'gtin']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    lookup_field = 'sku'
    
    # Add action to get all units for a product
    @action(detail=True, methods=['get'])
    def units(self, request, sku=None):
        """Get all units for a product"""
        product = self.get_object()
        units = product.units.all()
        
        # Apply filters if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            units = units.filter(status=status_filter)
            
        serializer = ProductUnitSerializer(units, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def add_to_batch(self, request):
        """
        Add a product to a receipt batch by SKU
        
        This endpoint allows adding a product to a batch by SKU in a single API call,
        which is especially useful for barcode scanner workflows.
        
        Required parameters:
        - sku: Product SKU
        - batch_id: UUID of the receipt batch
        - quantity: Quantity to add (default: 1)
        
        Optional parameters:
        - unit_cost: Unit cost
        - notes: Additional notes
        - requires_unit_qc: Whether units require QC (default: false)
        - create_product_units: Whether to create product units (default: true)
        - skip_inventory_receipt: Whether to skip inventory receipt (default: false)
        - process_immediately: Whether to process the batch immediately (default: false)
        
        Returns detailed information about the added product and updated batch.
        """
        # Validate required parameters
        sku = request.data.get('sku')
        batch_id = request.data.get('batch_id')
        quantity = int(request.data.get('quantity', 1))
        
        if not sku:
            return Response({
                "success": False,
                "message": "SKU is required"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if not batch_id:
            return Response({
                "success": False,
                "message": "batch_id is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if quantity <= 0:
            return Response({
                "success": False,
                "message": "Quantity must be greater than zero"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Look up the product
        try:
            from products.models import Product
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            return Response({
                "success": False,
                "message": f"Product with SKU '{sku}' not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Look up the batch
        try:
            from receiving.models import ReceiptBatch
            batch = ReceiptBatch.objects.get(id=batch_id)
        except ReceiptBatch.DoesNotExist:
            return Response({
                "success": False,
                "message": f"Receipt batch with ID '{batch_id}' not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get optional parameters
        unit_cost = request.data.get('unit_cost')
        if unit_cost:
            try:
                unit_cost = float(unit_cost)
            except (ValueError, TypeError):
                return Response({
                    "success": False,
                    "message": "unit_cost must be a valid number"
                }, status=status.HTTP_400_BAD_REQUEST)
        
        requires_unit_qc = request.data.get('requires_unit_qc', False)
        create_product_units = request.data.get('create_product_units', True)
        skip_inventory_receipt = request.data.get('skip_inventory_receipt', False)
        notes = request.data.get('notes', '')
        
        # Check if this product already exists in the batch
        from receiving.models import BatchItem
        existing_item = BatchItem.objects.filter(batch=batch, product=product).first()
        
        if existing_item:
            # Update existing item
            original_quantity = existing_item.quantity
            existing_item.quantity += quantity
            
            # Calculate weighted average cost if unit cost is provided
            if unit_cost:
                total_cost = (original_quantity * (existing_item.unit_cost or 0)) + (quantity * unit_cost)
                existing_item.unit_cost = total_cost / existing_item.quantity
            
            existing_item.notes = notes or existing_item.notes
            existing_item.save()
            
            # Update linked inventory receipt if it exists and not skipped
            if existing_item.inventory_receipt and not skip_inventory_receipt:
                receipt = existing_item.inventory_receipt
                receipt.quantity += quantity
                if unit_cost:
                    receipt.unit_cost = existing_item.unit_cost
                receipt.save()
            
            added_item = existing_item
            new_item_created = False
            
            logger.info(f"Updated existing item {existing_item.id} in batch {batch.id}, " 
                        f"added {quantity} units of product {product.id} ({product.sku})")
        else:
            # Create new batch item
            batch_item = BatchItem.objects.create(
                batch=batch,
                product=product,
                quantity=quantity,
                unit_cost=unit_cost,
                notes=notes,
                requires_unit_qc=requires_unit_qc,
                create_product_units=create_product_units,
                skip_inventory_receipt=skip_inventory_receipt
            )
            
            # Create inventory receipt if not skipped
            if not skip_inventory_receipt:
                from inventory.models import InventoryReceipt
                receipt_data = {
                    'product': product,
                    'quantity': quantity,
                    'location': batch.location,
                    'unit_cost': unit_cost,
                    'requires_unit_qc': requires_unit_qc,
                    'create_product_units': create_product_units,
                    'is_processed': False,
                    'reference': batch.reference,
                    'batch_code': batch.batch_code,
                    'batch': batch,
                    'created_by': request.user if request.user.is_authenticated else None,
                    'notes': notes
                }
                
                inventory_receipt = InventoryReceipt.objects.create(**receipt_data)
                
                # Set the one-way relationship
                batch_item.inventory_receipt = inventory_receipt
                batch_item.save(update_fields=['inventory_receipt'])
            
            added_item = batch_item
            new_item_created = True
            
            logger.info(f"Created new item {batch_item.id} in batch {batch.id}, " 
                        f"added {quantity} units of product {product.id} ({product.sku})")
        
        # Update batch totals
        batch.calculate_totals()
        
        # If batch was completed and new items added, update status
        if batch.status == 'completed':
            unprocessed_receipt = False
            if new_item_created and added_item.inventory_receipt and not added_item.inventory_receipt.is_processed:
                unprocessed_receipt = True
            
            if unprocessed_receipt:
                batch.status = 'pending'
                batch.save(update_fields=['status'])
        
        # Process immediately if requested
        process_immediately = request.data.get('process_immediately', False)
        process_result = None
        
        if process_immediately:
            try:
                process_result = batch.process_batch()
                logger.info(f"Processed batch {batch.id} after adding item")
            except Exception as e:
                logger.exception(f"Error processing batch {batch.id}: {str(e)}")
                # Note: We continue even if processing fails, to return info about the added item
        
        # Return detailed response
        from products.serializers import ProductMinimalSerializer
        from receiving.serializers import BatchItemSerializer
        
        # Use your existing minimal serializer instead of creating a new one
        product_data = ProductMinimalSerializer(product).data
        
        # Check if you have an existing brief batch serializer or create a simple dict
        try:
            from receiving.serializers import ReceiptBatchBriefSerializer
            batch_data = ReceiptBatchBriefSerializer(batch).data
        except ImportError:
            # Create a simple dict if the serializer doesn't exist
            batch_data = {
                'id': str(batch.id),
                'batch_code': batch.batch_code,
                'reference': batch.reference,
                'status': batch.status,
                'location_name': batch.location.name if batch.location else 'Unknown'
            }
        
        # Check if you have an existing batch item serializer or create a simple dict
        try:
            item_data = BatchItemSerializer(added_item).data
        except (ImportError, NameError):
            # Create a simple dict if the serializer doesn't exist
            item_data = {
                'id': str(added_item.id),
                'quantity': added_item.quantity,
                'unit_cost': added_item.unit_cost,
                'total_cost': added_item.quantity * (added_item.unit_cost or 0) if added_item.unit_cost else None
            }
        
        response_data = {
            "success": True,
            "message": f"Added {quantity} units of {product.name} to batch",
            "product": product_data,
            "batch": batch_data,
            "item": item_data,
            "new_item_created": new_item_created,
            "current_quantity": added_item.quantity,
            "previous_quantity": added_item.quantity - quantity if not new_item_created else 0,
        }
        
        if process_immediately:
            response_data["processed"] = bool(process_result)
            response_data["processed_message"] = "Batch processed successfully" if process_result else "Processing failed or was not needed"
        
        return Response(response_data, status=status.HTTP_200_OK)


class ProductUnitViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ProductUnits.
    Supports filtering and searching by status and serial number.
    """
    queryset = ProductUnit.objects.select_related('product').all()
    serializer_class = ProductUnitSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_serialized', 'created_at', 'product__sku']
    search_fields = ['serial_number', 'manufacturer_serial', 'product__name', 'product__sku']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-created_at']
    
    def create(self, request, *args, **kwargs):
        """
        Create a new product unit with proper validation.
        Calls the model's full_clean method to enforce all validations.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"Error creating product unit: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """
        Update a product unit with proper validation.
        Uses partial=True to allow partial updates (PATCH).
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        try:
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error updating product unit: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def sell(self, request, pk=None):
        """Mark a product unit as sold"""
        product_unit = self.get_object()
        
        # Optional: Get order item from request
        order_item_id = request.data.get('order_item_id')
        order_item = None
        
        if order_item_id:
            try:
                from orders.models import OrderItem
                order_item = OrderItem.objects.get(id=order_item_id)
                
                # Validate product match if order item is provided
                if order_item.product != product_unit.product:
                    return Response(
                        {'error': 'Product unit does not match order item product'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except OrderItem.DoesNotExist:
                return Response({'error': 'Order item not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            # Assume mark_as_sold is defined in your model
            product_unit.mark_as_sold(order_item=order_item)
            serializer = self.get_serializer(product_unit)
            return Response({'status': 'Product marked as sold', 'product_unit': serializer.data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def return_unit(self, request, pk=None):
        """Mark a product unit as returned"""
        product_unit = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response({'error': 'Reason is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if product_unit.status != 'sold':
                return Response(
                    {'error': 'Only sold products can be returned'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Store order item before clearing it
            old_order_item = product_unit.order_item
            
            # Update status
            product_unit.status = 'returned'
            product_unit.order_item = None
            product_unit.save()
            
            # Log the return if you have a history model
            if hasattr(product_unit, 'history'):
                product_unit.history.create(
                    action='returned',
                    details=f"Returned. Reason: {reason}",
                    order_item=old_order_item
                )
            
            serializer = self.get_serializer(product_unit)
            return Response({'status': 'Product marked as returned', 'product_unit': serializer.data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def restock(self, request, pk=None):
        """Return a product to inventory"""
        product_unit = self.get_object()
        
        try:
            if product_unit.status != 'returned':
                return Response(
                    {'error': 'Only returned products can be restocked'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update status
            product_unit.status = 'in_stock'
            product_unit.save()
            
            # Log the restock if you have a history model
            if hasattr(product_unit, 'history'):
                product_unit.history.create(
                    action='restocked',
                    details="Returned to inventory"
                )
            
            serializer = self.get_serializer(product_unit)
            return Response({'status': 'Product restocked', 'product_unit': serializer.data})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def bulk_create(self, request):
        """Create multiple product units at once"""
        try:
            product_id = request.data.get('product')
            quantity = int(request.data.get('quantity', 1))
            
            if quantity < 1:
                return Response(
                    {'error': 'Quantity must be at least 1'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if quantity > 50:
                return Response(
                    {'error': 'Cannot create more than 50 units at once'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                return Response(
                    {'error': f'Product with ID {product_id} not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # Create the units
            created_units = []
            for _ in range(quantity):
                unit = ProductUnit(
                    product=product,
                    status='in_stock',
                    is_serialized=True
                )
                unit.save()  # This will trigger serial number generation
                created_units.append(unit)
                
            # Serialize the created units
            serializer = self.get_serializer(created_units, many=True)
            return Response({
                'message': f'Successfully created {len(created_units)} product units',
                'units': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except ValueError:
            return Response(
                {'error': 'Invalid quantity'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in bulk create: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def update_manufacturer_serials(self, request):
        """Update manufacturer serial numbers in bulk"""
        try:
            serials_data = request.data.get('serials', [])
            if not serials_data or not isinstance(serials_data, list):
                return Response(
                    {'error': 'Expected list of serial mappings'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Expected format: [{"serial_number": "ABC123", "manufacturer_serial": "MFG456"}, ...]
            updated = 0
            errors = []
            
            for item in serials_data:
                serial = item.get('serial_number')
                mfg_serial = item.get('manufacturer_serial')
                
                if not serial or not mfg_serial:
                    errors.append(f"Missing serial_number or manufacturer_serial: {item}")
                    continue
                    
                try:
                    unit = ProductUnit.objects.get(serial_number=serial)
                    unit.manufacturer_serial = mfg_serial
                    unit.save()
                    updated += 1
                except ProductUnit.DoesNotExist:
                    errors.append(f"No product unit found with serial number: {serial}")
                except Exception as e:
                    errors.append(f"Error updating {serial}: {str(e)}")
                    
            return Response({
                'updated': updated,
                'errors': errors if errors else None
            })
        except Exception as e:
            logger.error(f"Error updating manufacturer serials: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign a product unit to an order item"""
        unit = self.get_object()
        order_item_id = request.data.get('order_item_id')
        ignore_qc = request.data.get('ignore_qc', False)
        notes = request.data.get('notes', '')
        
        if not order_item_id:
            return Response(
                {'error': 'order_item_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from orders.models import OrderItem
            order_item = OrderItem.objects.get(pk=order_item_id)
            
            # Check if product matches
            if order_item.product_id != unit.product_id:
                return Response(
                    {'error': 'Product unit does not match order item product'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Try to assign with QC handling
            unit.assign_to_order_item(
                order_item=order_item,
                user=request.user,
                notes=notes,
                ignore_qc=ignore_qc
            )
            
            serializer = self.get_serializer(unit)
            return Response({
                'status': 'Product unit assigned to order item',
                'product_unit': serializer.data
            })
            
        except OrderItem.DoesNotExist:
            return Response(
                {'error': 'Order item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error assigning product unit: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProductFamilyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ProductFamilies.
    Supports filtering, searching, and inventory aggregation.
    """
    queryset = ProductFamily.objects.all()
    serializer_class = ProductFamilySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product_type', 'is_active', 'manufacturer', 'model', 'category']
    search_fields = ['name', 'sku', 'manufacturer', 'model', 'description', 'keywords']
    ordering_fields = ['created_at', 'updated_at', 'name', 'manufacturer']
    ordering = ['name']
    
    def create(self, request, *args, **kwargs):
        """
        Create a new product family and optionally map a product to it in one step.
        
        If map_product_id is provided in the request data, after creating the family,
        the product will be mapped to this family automatically.
        
        If a family with the same SKU already exists, it will be returned instead of
        creating a duplicate.
        """
        # Extract and remove non-model fields
        map_product_id = request.data.pop('map_product_id', None)
        
        # Check for existing family with the same SKU
        sku = request.data.get('sku')
        existing_family = None
        
        if sku:
            try:
                existing_family = ProductFamily.objects.get(sku=sku)
                logger.info(f"Found existing family with SKU {sku}: {existing_family.name}")
            except ProductFamily.DoesNotExist:
                pass
                
        # If we found an existing family with this SKU
        if existing_family:
            mapping_success = False
            
            # Handle mapping if requested
            if map_product_id:
                try:
                    product = Product.objects.get(pk=map_product_id)
                    
                    # Check if already mapped to this family
                    if product.family and product.family.id == existing_family.id:
                        mapping_success = True
                    else:
                        # Map to this family
                        product.family = existing_family
                        product.save(update_fields=['family'])
                        mapping_success = True
                except Product.DoesNotExist:
                    logger.warning(f"Attempted to map non-existent product {map_product_id} to existing family {existing_family.id}")
                except Exception as e:
                    logger.error(f"Error mapping product to existing family: {e}")
            
            # Return the existing family
            response_data = self.get_serializer(existing_family).data
            response_data['mapping_success'] = mapping_success
            response_data['already_exists'] = True
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        # Standard create procedure for new family
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family = serializer.save()
          # Handle mapping if requested
        mapping_success = False
        if map_product_id:
            try:
                product = Product.objects.get(pk=map_product_id)
                product.family = family
                product.save(update_fields=['family'])
                mapping_success = True
            except Product.DoesNotExist:
                logger.warning(f"Attempted to map non-existent product {map_product_id} to family {family.id}")
            except Exception as e:
                logger.error(f"Error mapping product to family during creation: {e}")
        
        # Return the serialized family with mapping result
        headers = self.get_success_headers(serializer.data)
        response_data = serializer.data
        response_data['mapping_success'] = mapping_success
        
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
    
    @action(detail=False, methods=['post'])
    def suggest_matches(self, request):
        """
        Find product families that match the provided product attributes.
        
        This endpoint analyzes the provided product data and returns
        matching product families with a calculated match score.
        """
        # Extract product attributes from request data
        manufacturer = request.data.get('manufacturer')
        model = request.data.get('model')
        processor = request.data.get('processor')
        product_type = request.data.get('product_type')
        
        # Base queryset - start with all active families
        queryset = ProductFamily.objects.filter(is_active=True)
        
        # Apply filters based on available attributes
        filters = {}
        
        if product_type:
            filters['product_type'] = product_type
        
        # Initial filtering to narrow down candidates
        if filters:
            queryset = queryset.filter(**filters)
        
        # Get all potential matches for further processing
        potential_matches = list(queryset)
        results = []
        
        # Calculate match scores
        for family in potential_matches:
            match_score = 0
            total_fields = 0
            
            # Match manufacturer
            if manufacturer and family.manufacturer:
                total_fields += 1
                if manufacturer.lower() == family.manufacturer.lower():
                    match_score += 1
            
            # Match model
            if model and family.model:
                total_fields += 1
                if model.lower() == family.model.lower():
                    match_score += 1
            
            # Match processor if available
            if processor and family.attributes and 'processor' in family.attributes:
                total_fields += 1
                if processor.lower() == family.attributes['processor'].lower():
                    match_score += 1
            
            # Calculate percentage score
            percentage = round((match_score / max(total_fields, 1)) * 100)
            
            # Only include families with a minimum match score
            if percentage >= 40 or (manufacturer and family.manufacturer and manufacturer.lower() == family.manufacturer.lower()):
                results.append({
                    **ProductFamilySerializer(family).data,
                    'match_percentage': percentage
                })
        
        # Sort by match percentage (descending)
        results.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        return Response(results)
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in this family"""
        family = self.get_object()
        products = family.products.all()
        
        # Apply filters if provided
        platform = request.query_params.get('platform')
        if platform:
            products = products.filter(platform=platform)
            
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            products = products.filter(is_active=is_active_bool)
        
        # Use your existing product serializer
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def inventory(self, request, pk=None):
        """Get aggregated inventory for this family"""
        family = self.get_object()
        
        # Get basic inventory stats
        inventory_stats = family.total_inventory
        
        # Get additional inventory details by location
        from inventory.models import Inventory
        from django.db.models import Sum
        
        location_inventory = Inventory.objects.filter(
            product__family=family
        ).values(
            'location__name', 
            'location__id'
        ).annotate(
            total_quantity=Sum('quantity'),
            available_quantity=Sum('available_quantity')
        ).order_by('location__name')
        
        # Return detailed response
        response_data = {
            'family': {
                'id': str(family.id),
                'name': family.name,
                'sku': family.sku
            },
            'total_inventory': inventory_stats,
            'locations': location_inventory,
            'product_count': family.products.count()
        }
        
        return Response(response_data)
    @action(detail=False, methods=['post'], url_path='add_product', url_name='add_product')
    @transaction.atomic
    def add_product(self, request):
        """Add an existing product to a family"""
        family_id = request.data.get('family_id')
        product_id = request.data.get('product_id')
        
        if not family_id or not product_id:
            return Response({
                'error': 'Both family_id and product_id are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            family = ProductFamily.objects.get(pk=family_id)
            product = Product.objects.get(pk=product_id)
            
            # Check if product is already associated with this family
            if product.family and product.family.id == family.id:
                # Product is already in this family, return success
                return Response({
                    'success': True,
                    'message': f'Product {product.name} is already in family {family.name}',
                    'product': {
                        'id': str(product.id),
                        'name': product.name,
                        'sku': product.sku
                    },
                    'family': {
                        'id': str(family.id),
                        'name': family.name,
                        'sku': family.sku,
                        'product_count': family.products.count()
                    }
                })
                
            # Check if product is in a different family
            if product.family and product.family.id != family.id:
                # Product is in a different family, log this but proceed
                logger.info(f"Moving product {product.id} from family {product.family.id} to family {family.id}")
            
            # Associate product with family
            product.family = family
            product.save(update_fields=['family'])
            
            return Response({
                'success': True,
                'message': f'Added {product.name} to family {family.name}',
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'sku': product.sku
                },
                'family': {
                    'id': str(family.id),
                    'name': family.name,
                    'sku': family.sku,
                    'product_count': family.products.count()
                }
            })
            
        except ProductFamily.DoesNotExist:
            return Response({
                'error': f'Family with ID {family_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Product.DoesNotExist:
            return Response({
                'error': f'Product with ID {product_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error adding product to family: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def bulk_add_products(self, request, pk=None):
        """Add multiple products to this family"""
        family = self.get_object()
        product_ids = request.data.get('product_ids', [])
        
        if not product_ids or not isinstance(product_ids, list):
            return Response({
                'error': 'product_ids list is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        products_added = []
        errors = []
        
        for product_id in product_ids:
            try:
                product = Product.objects.get(pk=product_id)
                product.family = family
                product.save(update_fields=['family'])
                products_added.append({
                    'id': str(product.id),
                    'name': product.name,
                    'sku': product.sku
                })
            except Product.DoesNotExist:
                errors.append(f'Product with ID {product_id} not found')
            except Exception as e:
                errors.append(f'Error adding product {product_id}: {str(e)}')
        
        return Response({
            'success': True,
            'message': f'Added {len(products_added)} products to family {family.name}',
            'family': {
                'id': str(family.id),
                'name': family.name,
                'sku': family.sku,
                'product_count': family.products.count()
            },
            'products_added': products_added,
            'errors': errors if errors else None
        })
    
    @action(detail=True, methods=['post'])
    def remove_product(self, request, pk=None):
        """Remove a product from this family"""
        family = self.get_object()
        product_id = request.data.get('product_id')
        
        if not product_id:
            return Response({
                'error': 'product_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(pk=product_id)
            
            if product.family_id != family.id:
                return Response({
                    'error': f'Product {product.name} is not in this family'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Remove from family
            product.family = None
            product.save(update_fields=['family'])
            
            return Response({
                'success': True,
                'message': f'Removed {product.name} from family {family.name}',
                'product': {
                    'id': str(product.id),
                    'name': product.name,
                    'sku': product.sku
                },
                'family': {
                    'id': str(family.id),
                    'name': family.name,
                    'sku': family.sku,
                    'product_count': family.products.count()
                }
            })
            
        except Product.DoesNotExist:
            return Response({
                'error': f'Product with ID {product_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error removing product from family: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def get_or_create(self, request):
        """
        Get an existing family or create a new one, with product mapping support.
        
        This endpoint can be used to:
        1. Check if a family exists with the given SKU
        2. If it exists, optionally map a product to it
        3. If it doesn't exist, create it and optionally map a product
        
        This helps avoid duplicate families and simplifies client-side logic.
        """
        # Extract product_id separately
        map_product_id = request.data.get('map_product_id')
        
        # Look for existing family by SKU
        sku = request.data.get('sku')
        if not sku:
            return Response({
                'error': 'SKU is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Try to find an existing family
            existing_family = ProductFamily.objects.get(sku=sku)
            logger.info(f"Found existing family with SKU {sku}: {existing_family.name}")
            
            # Handle product mapping if requested
            mapping_success = False
            if map_product_id:
                try:
                    product = Product.objects.get(pk=map_product_id)
                    
                    # Check if already mapped to this family
                    if product.family and product.family.id == existing_family.id:
                        mapping_success = True
                        logger.info(f"Product {map_product_id} already mapped to family {existing_family.id}")
                    else:
                        # Map to this family
                        product.family = existing_family
                        product.save(update_fields=['family'])
                        mapping_success = True
                        logger.info(f"Successfully mapped product {map_product_id} to existing family {existing_family.id}")
                except Product.DoesNotExist:
                    logger.warning(f"Attempted to map non-existent product {map_product_id} to existing family {existing_family.id}")
                except Exception as e:
                    logger.error(f"Error mapping product {map_product_id} to existing family {existing_family.id}: {e}")
            
            # Return the existing family
            response_data = self.get_serializer(existing_family).data
            response_data['mapping_success'] = mapping_success
            response_data['was_created'] = False
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ProductFamily.DoesNotExist:
            # Family doesn't exist, create it
            logger.info(f"No existing family found with SKU {sku}, creating new one")
            
            # Prepare data for serializer (removing map_product_id if present)
            data = request.data.copy()
            if 'map_product_id' in data:
                data.pop('map_product_id')
                
            # Create the new family
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            family = serializer.save()
            
            # Handle product mapping if requested
            mapping_success = False
            if map_product_id:
                try:
                    product = Product.objects.get(pk=map_product_id)
                    product.family = family
                    product.save(update_fields=['family'])
                    mapping_success = True
                    logger.info(f"Successfully mapped product {map_product_id} to new family {family.id}")
                except Product.DoesNotExist:
                    logger.warning(f"Attempted to map non-existent product {map_product_id} to new family {family.id}")
                except Exception as e:
                    logger.error(f"Error mapping product {map_product_id} to new family {family.id}: {e}")
            
            # Return the new family
            response_data = serializer.data
            response_data['mapping_success'] = mapping_success
            response_data['was_created'] = True
            
            return Response(response_data, status=status.HTTP_201_CREATED)

# Set up router and URLs
# router = routers.DefaultRouter()
# router.register(r'products', ProductViewSet)
# router.register(r'units', ProductUnitViewSet)
# # router.register(r'families', ProductFamilyViewSet)

# urlpatterns = [
#     path('', include(router.urls)),
# ]