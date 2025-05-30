from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import QualityControl, QualityControlStatus, ProductUnitQC, ProductQCTemplate
from .serializers import (
    QualityControlSerializer, QualityControlDetailSerializer,
    ProductUnitQCSerializer, ProductUnitQCDetailSerializer
)
from inventory.models import Location
from products.models import ProductUnit, Product
from .services import QualityControlService
from .utils import (
    get_visual_testing_schema, get_functional_testing_schema,
    get_electrical_testing_schema, get_packaging_testing_schema,
    get_measurements_schema, get_specs_schema, merge_testing_data
)

@staff_member_required
def inspect_quality_control(request, pk):
    """Handle QC inspection from admin"""
    qc = get_object_or_404(QualityControl, pk=pk)
    
    if request.method == 'POST':
        try:
            approved_qty = int(request.POST.get('approved_quantity', 0))
            rejected_qty = int(request.POST.get('rejected_quantity', 0))
            inspection_notes = request.POST.get('inspection_notes', '')
            
            QualityControlService.process_inspection(
                qc, approved_qty, rejected_qty, inspection_notes, request.user
            )
            
            messages.success(
                request, 
                f"Inspection completed: {approved_qty} approved, {rejected_qty} rejected."
            )
            
            # Offer to create receipt if approved
            if approved_qty > 0:
                return redirect('admin:create_receipt_from_qc', pk=pk)
                
            return redirect('admin:quality_control_qualitycontrol_changelist')
            
        except ValueError as e:
            messages.error(request, str(e))
            
    # Show inspection form
    context = {
        'title': f"Inspect: {qc}",
        'qc': qc,
        'opts': QualityControl._meta,
        'app_label': QualityControl._meta.app_label,
        'original': qc,
    }
    return render(request, 'admin/quality_control/inspect_qc.html', context)

@staff_member_required
def create_inventory_receipt(request, pk):
    """Create inventory receipt from approved QC"""
    qc = get_object_or_404(QualityControl, pk=pk)
    
    if qc.inventory_receipt:
        messages.info(request, "Receipt already exists for this QC")
        return redirect(
            'admin:inventory_inventoryreceipt_change', 
            object_id=qc.inventory_receipt.pk
        )
    
    if request.method == 'POST':
        try:
            location_id = request.POST.get('location')
            location = Location.objects.get(id=location_id)
            
            receipt = QualityControlService.create_receipt_from_qc(
                qc, location, request.user
            )
            
            messages.success(
                request,
                f"Inventory receipt created with {receipt.quantity} units. "
                f"ProductUnits will be generated."
            )
            return redirect('admin:inventory_inventoryreceipt_change', object_id=receipt.pk)
            
        except Exception as e:
            messages.error(request, f"Error creating receipt: {str(e)}")
    
    # Show location selection form
    locations = Location.objects.filter(is_active=True)
    
    context = {
        'title': "Create Inventory Receipt",
        'qc': qc,
        'locations': locations,
        'opts': QualityControl._meta,
        'app_label': QualityControl._meta.app_label,
    }
    return render(request, 'admin/quality_control/create_receipt.html', context)

class QualityControlViewSet(viewsets.ModelViewSet):
    """API endpoint for quality control records"""
    queryset = QualityControl.objects.all().order_by('-created_at')
    serializer_class = QualityControlSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'product', 'created_at']
    search_fields = ['reference', 'batch_code', 'product__name', 'product__sku']
    ordering_fields = ['created_at', 'updated_at', 'product__name']
    ordering = ['-created_at']
    service_class = QualityControlService
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return QualityControlDetailSerializer
        return QualityControlSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def complete_inspection(self, request, pk=None):
        """API endpoint to complete inspection"""
        qc = self.get_object()
        
        approved_qty = request.data.get('approved_quantity')
        rejected_qty = request.data.get('rejected_quantity')
        inspection_notes = request.data.get('inspection_notes', '')
        
        if approved_qty is None or rejected_qty is None:
            return Response({
                'error': 'Both approved and rejected quantities are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            self.service_class.process_inspection(
                qc, int(approved_qty), int(rejected_qty), inspection_notes, request.user
            )
            return Response({
                'status': 'success',
                'qc': QualityControlSerializer(qc).data
            })
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def create_receipt(self, request, pk=None):
        """API endpoint to create inventory receipt from QC"""
        qc = self.get_object()
        
        if qc.inventory_receipt:
            return Response({
                'error': 'Receipt already exists',
                'receipt_id': qc.inventory_receipt.id
            }, status=status.HTTP_400_BAD_REQUEST)
            
        location_id = request.data.get('location_id')
        requires_unit_qc = request.data.get('requires_unit_qc', False)
        
        if not location_id:
            return Response({
                'error': 'location_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            from inventory.models import Location
            location = Location.objects.get(pk=location_id)
            
            receipt = self.service_class.create_receipt_from_qc(
                qc, location, request.user, requires_unit_qc
            )
            
            from products.models import ProductUnit
            unit_count = ProductUnit.objects.filter(
                metadata__receipt_id=str(receipt.id)
            ).count()
            
            pending_qc = 0
            if requires_unit_qc:
                pending_qc = ProductUnit.objects.filter(
                    status='pending_qc', 
                    metadata__receipt_id=str(receipt.id)
                ).count()
            
            from inventory.serializers import InventoryReceiptSerializer
            
            return Response({
                'status': 'success',
                'message': f"Created receipt with {unit_count} units",
                'receipt': InventoryReceiptSerializer(receipt).data,
                'units_created': unit_count,
                'units_pending_qc': pending_qc,
                'requires_unit_qc': requires_unit_qc
            })
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class ProductUnitQCViewSet(viewsets.ModelViewSet):
    """API endpoint for unit-level quality control"""
    queryset = ProductUnitQC.objects.all().select_related('unit', 'batch_qc', 'tested_by')
    serializer_class = ProductUnitQCSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['passed', 'grade', 'tested_by', 'batch_qc']
    search_fields = ['unit__serial_number', 'test_notes']
    ordering_fields = ['tested_at', 'updated_at', 'grade']
    ordering = ['-tested_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductUnitQCDetailSerializer
        return ProductUnitQCSerializer
    
    def perform_create(self, serializer):
        serializer.save(tested_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def pending_units(self, request):
        """Get units pending QC"""
        pending_units = ProductUnit.objects.filter(status='pending_qc')
        from products.serializers import ProductUnitSerializer
        serializer = ProductUnitSerializer(pending_units, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def perform_qc(self, request):
        """Perform QC on a specific unit with template pre-filling"""
        unit_id = request.data.get('unit')
        if not unit_id:
            return Response({
                'error': 'Unit ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            from products.models import ProductUnit
            unit = ProductUnit.objects.get(pk=unit_id)
        except ProductUnit.DoesNotExist:
            return Response({
                'error': 'Unit not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if hasattr(unit, 'qc_details'):
            return Response({
                'error': 'QC already performed for this unit',
                'qc_id': str(unit.qc_details.id)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get batch QC if it exists
        batch_qc = None
        if unit.metadata and 'qc' in unit.metadata and 'qc_id' in unit.metadata['qc']:
            qc_id = unit.metadata['qc']['qc_id']
            try:
                batch_qc = QualityControl.objects.get(pk=qc_id)
            except QualityControl.DoesNotExist:
                pass
        
        # Create QC record with default/template values
        qc_record = ProductUnitQC(
            unit=unit,
            batch_qc=batch_qc,
            tested_by=request.user
        )
        
        # Initialize from template (or default schemas)
        qc_record.initialize_from_template()
        
        # Update with request data
        data = request.data.copy()
        
        # Update each testing field if provided in request
        for field in ['visual_testing', 'functional_testing', 
                      'electrical_testing', 'packaging_testing',
                      'measurements', 'specs']:
            if field in data:
                # Merge existing template with provided data
                current_value = getattr(qc_record, field)
                merged = merge_testing_data(current_value, data[field])
                setattr(qc_record, field, merged)
        
        # Set other fields
        if 'test_notes' in data:
            qc_record.test_notes = data['test_notes']
            
        if 'grade' in data:
            qc_record.grade = data['grade']
            
        if 'qc_image' in request.FILES:
            qc_record.qc_image = request.FILES['qc_image']
        
        try:
            qc_record.save()
            
            return Response({
                'status': 'success',
                'message': f"QC completed with grade {qc_record.grade}",
                'passed': qc_record.passed,
                'qc': ProductUnitQCSerializer(qc_record).data
            })
        except ValidationError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def template(self, request):
        """Get QC template for a specific product"""
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({
                'error': 'product_id query parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response({
                'error': 'Product not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        template = ProductQCTemplate.get_template_for_product(product)
        
        if not template:
            # Return default schemas
            return Response({
                'product': product.id,
                'product_name': product.name,
                'visual_testing': get_visual_testing_schema(),
                'functional_testing': get_functional_testing_schema(),
                'electrical_testing': get_electrical_testing_schema(),
                'packaging_testing': get_packaging_testing_schema(),
                'measurements': get_measurements_schema(),
                'specs': get_specs_schema(),
                'required_tests': {
                    'visual_testing': True,
                    'functional_testing': True,
                    'electrical_testing': True,
                    'packaging_testing': True
                }
            })
        
        # Return product-specific template
        return Response({
            'template_id': template.id,
            'template_name': template.name,
            'product_type': template.product_type.name,
            'visual_testing': template.visual_testing_template,
            'functional_testing': template.functional_testing_template,
            'electrical_testing': template.electrical_testing_template,
            'packaging_testing': template.packaging_testing_template,
            'measurements': template.measurements_template,
            'specs': template.specs_template,
            'required_tests': {
                'visual_testing': template.visual_testing_required,
                'functional_testing': template.functional_testing_required,
                'electrical_testing': template.electrical_testing_required,
                'packaging_testing': template.packaging_testing_required
            }
        })
    
#------------------------------------------------------------------------------------------#
#--------------------------MOBILE APP API FOR QC SIMPLIFIED INTERFACE----------------------#
#------------------------------------------------------------------------------------------#
    
    @action(detail=False, methods=['get'])
    def mobile_workflow(self, request):
        """Get next batch of units pending QC for mobile app"""
        limit = int(request.query_params.get('limit', 10))
        
        # Get units pending QC
        pending_units = ProductUnit.objects.filter(status='pending_qc')[:limit]
        
        from products.serializers import ProductUnitSerializer
        return Response({
            'pending_count': pending_units.count(),
            'units': ProductUnitSerializer(pending_units, many=True).data,
        })

    @action(detail=False, methods=['post'])
    def mobile_qc_submit(self, request):
        """Submit QC results from mobile app with simplified interface"""
        unit_id = request.data.get('unit_id')
        passed = request.data.get('passed', False)
        grade = request.data.get('grade', 'C')
        
        # Additional fields with simplified structure for mobile app
        notes = request.data.get('notes', '')
        visual_approved = request.data.get('visual_ok', False)
        functional_approved = request.data.get('functional_ok', False)
        electrical_approved = request.data.get('electrical_ok', False)
        packaging_approved = request.data.get('packaging_ok', False)
        
        # Transform to full QC structure
        from .utils import get_visual_testing_schema, get_functional_testing_schema
        
        visual = get_visual_testing_schema()
        visual['approved'] = visual_approved
        
        functional = get_functional_testing_schema()
        functional['approved'] = functional_approved
        
        # Build request to regular endpoint
        full_data = {
            'unit': unit_id,
            'grade': grade,
            'test_notes': notes,
            'visual_testing': visual,
            'functional_testing': functional,
            'electrical_testing': {'approved': electrical_approved},
            'packaging_testing': {'approved': packaging_approved}
        }
        
        # Pass to regular perform_qc method
        request._full_data = full_data
        return self.perform_qc(request)