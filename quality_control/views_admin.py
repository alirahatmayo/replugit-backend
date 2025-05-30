from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required

from .models import QualityControl
from inventory.models import Location
from .services import QualityControlService

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