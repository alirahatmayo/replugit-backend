from django.db import models

# Create your models here.
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError

class QualityControlStatus(models.TextChoices):
    PENDING = 'pending', 'Pending Inspection'
    IN_PROGRESS = 'in_progress', 'Inspection In Progress'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    PARTIALLY_APPROVED = 'partially_approved', 'Partially Approved'

class QualityControl(models.Model):
    """
    Simple model for tracking product quality control before sending to inventory.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic information
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    received_quantity = models.PositiveIntegerField(default=0)
    approved_quantity = models.PositiveIntegerField(default=0)
    rejected_quantity = models.PositiveIntegerField(default=0)
    
    # Reference information
    reference = models.CharField(max_length=100, blank=True, null=True, help_text="PO number or reference")
    batch_code = models.CharField(max_length=50, blank=True, null=True)
    carrier = models.CharField(max_length=100, blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=QualityControlStatus.choices,
        default=QualityControlStatus.PENDING
    )
    
    # Optional supplier information - stored as JSON 
    supplier_info = models.JSONField(null=True, blank=True)
    
    # Notes about the inspection
    notes = models.TextField(blank=True, null=True)
    inspection_notes = models.TextField(blank=True, null=True)
    
    # Related inventory receipt (created after approval)
    inventory_receipt = models.OneToOneField(
        'inventory.InventoryReceipt',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quality_control'
    )
    
    # User tracking
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_qc'
    )
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inspected_qc'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    inspected_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"QC-{self.created_at.strftime('%y%m%d')}-{self.product.sku} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-update status based on quantities
        if self.approved_quantity > 0 and self.approved_quantity < self.received_quantity:
            self.status = QualityControlStatus.PARTIALLY_APPROVED
        elif self.approved_quantity >= self.received_quantity:
            self.status = QualityControlStatus.APPROVED
        elif self.rejected_quantity >= self.received_quantity:
            self.status = QualityControlStatus.REJECTED
            
        super().save(*args, **kwargs)
    
    def complete_inspection(self, approved_qty, rejected_qty, notes, inspected_by):
        """
        Complete the inspection with approval/rejection quantities
        """
        if approved_qty + rejected_qty > self.received_quantity:
            raise ValueError("Sum of approved and rejected quantities cannot exceed received quantity")
            
        self.approved_quantity = approved_qty
        self.rejected_quantity = rejected_qty
        self.inspection_notes = notes
        self.inspected_by = inspected_by
        self.inspected_at = timezone.now()
        
        # Update status based on quantities
        if approved_qty == 0:
            self.status = QualityControlStatus.REJECTED
        elif approved_qty == self.received_quantity:
            self.status = QualityControlStatus.APPROVED
        else:
            self.status = QualityControlStatus.PARTIALLY_APPROVED
            
        self.save()
        return True
    
    def create_inventory_receipt(self, location, created_by=None):
        """
        Create an inventory receipt from the approved quantity
        """
        from inventory.models import InventoryReceipt
        
        if self.status not in [QualityControlStatus.APPROVED, QualityControlStatus.PARTIALLY_APPROVED]:
            raise ValueError("Cannot create inventory receipt - QC not approved")
            
        if self.approved_quantity <= 0:
            raise ValueError("Cannot create inventory receipt - No approved items")
            
        if self.inventory_receipt:
            raise ValueError("Inventory receipt already exists for this QC")
        
        # Create the inventory receipt
        receipt = InventoryReceipt.objects.create(
            product=self.product,
            quantity=self.approved_quantity,
            location=location,
            reference=f"From QC: {self.reference or str(self.id)[:8]}",
            batch_code=self.batch_code,
            notes=f"Quality Control approved: {self.inspection_notes or ''}",
            seller_info=self.supplier_info,
            created_by=created_by or self.inspected_by or self.created_by
        )
        
        # Link back to this QC
        self.inventory_receipt = receipt
        self.save()
        
        return receipt
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Quality Control"
        verbose_name_plural = "Quality Controls"

class ProductUnitQC(models.Model):
    """
    QC results for individual product units.
    
    Testing details are stored in JSONFields for future extensibility.
    The overall grade is provided manually, while the 'passed' flag is 
    automatically computed based on each test's 'approved' flag.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.OneToOneField('products.ProductUnit', on_delete=models.CASCADE, related_name='qc_details')
    batch_qc = models.ForeignKey('quality_control.QualityControl', on_delete=models.SET_NULL,
                                 null=True, related_name='unit_qcs')
    
    # JSONFields for test details
    visual_testing = models.JSONField(default=dict, help_text="Visual inspection details")
    functional_testing = models.JSONField(default=dict, help_text="Functional test details")
    electrical_testing = models.JSONField(default=dict, help_text="Electrical test details")
    packaging_testing = models.JSONField(default=dict, help_text="Packaging inspection details")
    
    # Common measurements and specs
    measurements = models.JSONField(default=dict, help_text="Measurements (e.g., power, weight)")
    specs = models.JSONField(default=dict, help_text="Device specifications")
    
    test_notes = models.TextField(blank=True, null=True)
    tested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, related_name='tested_units')
    tested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # QC result
    passed = models.BooleanField(default=True, help_text="Overall QC result computed from tests")
    
    # Manual grading field
    GRADE_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('F', 'F'),
    ]
    grade = models.CharField(
        max_length=1,
        choices=GRADE_CHOICES,
        default='F',
        help_text="Overall QC Grade (manual input)"
    )
    
    qc_image = models.ImageField(upload_to='qc_images/', null=True, blank=True,
                                 help_text="Image captured during QC")
    
    def initialize_from_template(self):
        """Initialize QC fields from product-specific template if available"""
        from .utils import initialize_qc_with_template
        initialize_qc_with_template(self)
    
    def clean(self):
        """
        Auto-calculate the overall 'passed' flag based on the 'approved' flag in each testing JSON.
        Also ensure all JSON fields have proper structure using templates or default schemas.
        """
        # Initialize from template or default schemas
        self.initialize_from_template()
        
        # Check for required tests based on product type template
        from .models import ProductQCTemplate
        template = None
        if self.unit and hasattr(self.unit, 'product'):
            template = ProductQCTemplate.get_template_for_product(self.unit.product)
        
        tests = [self.visual_testing, self.functional_testing, 
                 self.electrical_testing, self.packaging_testing]
        test_names = ['Visual', 'Functional', 'Electrical', 'Packaging']
        
        required_tests = []
        
        # If we have a template, check which tests are required
        if template:
            required_flags = [
                template.visual_testing_required,
                template.functional_testing_required,
                template.electrical_testing_required,
                template.packaging_testing_required
            ]
            
            for i, required in enumerate(required_flags):
                if required:
                    required_tests.append((i, test_names[i]))
        else:
            # Default: all tests are required
            for i, name in enumerate(test_names):
                required_tests.append((i, name))
        
        # Ensure each required test has an 'approved' key
        for i, test_type in required_tests:
            if not tests[i]:
                # If missing but required, raise error
                raise ValidationError(f"{test_type} testing is required but missing")
                
            if 'approved' not in tests[i]:
                raise ValidationError(f"{test_type} testing must include an 'approved' flag")
        
        # Calculate overall pass status - only from tests with data
        valid_tests = [test for test in tests if test]
        if valid_tests:
            self.passed = all(test.get('approved', False) for test in valid_tests)
        else:
            # If no tests have been performed, default to not passed
            self.passed = False
            
        super().clean()
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update unit status based on QC result
        if self.unit:
            from products.models import ProductUnit
            if hasattr(ProductUnit, 'STATUS_CHOICES') and hasattr(self.unit, 'status'):
                if self.passed:
                    self.unit.status = 'in_stock'
                else:
                    self.unit.status = 'defective'
                # Save without triggering recursion
                ProductUnit.objects.filter(pk=self.unit.pk).update(status=self.unit.status)
    
    class Meta:
        ordering = ['-tested_at']
        verbose_name = "Product Unit QC"
        verbose_name_plural = "Product Unit QC Records"
    
    def __str__(self):
        return f"QC {self.grade} - {self.unit} on {self.tested_at:%Y-%m-%d}"

class ProductQCTemplate(models.Model):
    """
    Product-specific QC template with customized testing requirements.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    product_type_name = models.CharField(max_length=100)  # Simple string field
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    
    # Template structures for each test type
    visual_testing_template = models.JSONField(default=dict)
    functional_testing_template = models.JSONField(default=dict)
    electrical_testing_template = models.JSONField(default=dict) 
    packaging_testing_template = models.JSONField(default=dict)
    measurements_template = models.JSONField(default=dict)
    specs_template = models.JSONField(default=dict)
    
    # Required tests for this product type
    visual_testing_required = models.BooleanField(default=True)
    functional_testing_required = models.BooleanField(default=True) 
    electrical_testing_required = models.BooleanField(default=True)
    packaging_testing_required = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_qc_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['product_type_name', '-created_at']
        verbose_name = "Product QC Template"
        verbose_name_plural = "Product QC Templates"
        
    def __str__(self):
        return f"{self.name} - {self.product_type_name}"
    
    def save(self, *args, **kwargs):
        # If updating an existing template, create a new version
        if self.pk:
            latest = ProductQCTemplate.objects.filter(
                product_type_name=self.product_type_name,
                name=self.name
            ).order_by('-version').first()
            
            if latest:
                self.pk = None  # Force create new
                self.version = latest.version + 1
        
        from .utils import initialize_template_schemas
        initialize_template_schemas(self)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_template_for_product(cls, product):
        """Get the appropriate QC template for a product"""
        # This is correct if product.product_type is a string - if it's an object with a name attribute
        if not hasattr(product, 'product_type'):
            return None
            
        # Get the type name - handle both string and object cases
        type_name = product.product_type
        if not isinstance(type_name, str):
            type_name = getattr(product.product_type, 'name', str(product.product_type))
            
        template = cls.objects.filter(
            product_type_name=type_name,
            is_active=True
        ).order_by('-created_at').first()
        
        return template

class QCFieldDefinition(models.Model):
    """Define custom QC fields for different product types"""
    # Change from ForeignKey to CharField
    product_type_name = models.CharField(max_length=100)  # Simple string field
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(
        max_length=20,
        choices=[
            ('boolean', 'Boolean'),
            ('number', 'Number'),
            ('string', 'Text'),
            ('enum', 'Enumeration'),
            ('image', 'Image'),
        ],
        default='boolean'
    )
    test_category = models.CharField(
        max_length=30,
        choices=[
            ('visual', 'Visual Testing'),
            ('functional', 'Functional Testing'),
            ('electrical', 'Electrical Testing'),
            ('packaging', 'Packaging Testing'),
            ('measurements', 'Measurements'),
            ('specs', 'Specifications'),
        ]
    )
    required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    enum_options = models.JSONField(null=True, blank=True, help_text='List of options for enum type')
    display_order = models.PositiveIntegerField(default=100)
    
    class Meta:
        ordering = ['test_category', 'display_order', 'field_name']
        unique_together = ['product_type_name', 'test_category', 'field_name']  # Updated