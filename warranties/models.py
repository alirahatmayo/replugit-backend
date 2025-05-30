from django.db import models, transaction
from django.utils.timezone import now
from datetime import timedelta

from django.core.exceptions import ValidationError

class Warranty(models.Model):
    """
    Represents a warranty associated with a product unit.
    Tracks warranty lifecycle and extensions.
    """
    product_unit = models.OneToOneField('products.ProductUnit', on_delete=models.CASCADE)
    customer = models.ForeignKey('customers.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, null=True, blank=True, related_name='warranties')
    purchase_date = models.DateField()
    warranty_period = models.PositiveIntegerField(default=3, help_text="Initial warranty period in months.")
    extended_period = models.PositiveIntegerField(default=0, help_text="Additional warranty period in months.")
    warranty_expiration_date = models.DateField(null=True, blank=True)
    is_extended = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ('not_registered', 'Not Registered'),
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('void', 'Void'),
        ],
        default='not_registered',
    )
    comments = models.TextField(null=True, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    max_extensions = models.PositiveIntegerField(default=2, help_text="Maximum allowed extensions.")

    class Meta:
        verbose_name = "Warranty"
        verbose_name_plural = "Warranties"
        ordering = ['-last_updated']

    def is_expired(self):
        """
        Check if the warranty is expired without modifying its state.
        """
        if not self.warranty_expiration_date:
            return False
        return now().date() > self.warranty_expiration_date

    def check_and_update_expiration(self):
        """
        Automatically update the warranty status to 'expired' if applicable.
        """
        if self.is_expired() and self.status == 'active':
            self.transition_status('expired')

    def can_transition_to(self, new_status):
        """
        Validate if a status transition is allowed.
        """
        valid_transitions = {
            'not_registered': ['active', 'void'],
            'active': ['expired', 'void'],
            'expired': ['void'],
            'void': [],
        }
        return new_status in valid_transitions.get(self.status, [])

    @transaction.atomic
    def transition_status(self, new_status, user=None):
        """
        Transition the warranty to a new status.
        
        Args:
            new_status: The new status to transition to
            user: The user performing the action
            
        Returns:
            bool: True if status was changed
            
        Raises:
            ValidationError: If status transition is not allowed
        """
        if self.status == new_status:
            return False
        
        if not self.can_transition_to(new_status):
            raise ValidationError(f"Cannot transition from {self.status} to {new_status}")
        
        # Update status
        old_status = self.status
        self.status = new_status
        self.save()
        
        # Create log entry ONLY if this is not an admin edit
        # (admin edits are already logged in admin.save_model)
        if not hasattr(self, '_admin_edit') or not self._admin_edit:
            self.logs.create(
                action=new_status,
                performed_by=user,
                details=f"Status changed from {old_status} to {new_status}"
            )
        
        return True

    @transaction.atomic
    def extend_warranty(self, months):
        """
        Extend the warranty period by a specified number of months.
        """
        if months <= 0:
            raise ValidationError("Extension period must be positive.")
        if self.is_expired():
            raise ValidationError("Cannot extend an expired warranty.")
        if self.warranty_period + self.extended_period + months > self.max_extensions * self.warranty_period:
            raise ValidationError("Maximum extension limit reached.")

        self.extended_period += months
        self.warranty_expiration_date = self.purchase_date + timedelta(days=30 * (self.warranty_period + self.extended_period))
        self.is_extended = True
        self.save()
        

    @transaction.atomic
    def reset_warranty(self, user=None, reason=None, keep_customer=False):
        """
        Reset a warranty to 'not_registered' status for reuse.
        
        This generic method can be used for returns, exchanges, or any scenario
        where a warranty needs to be reset.
        
        Args:
            user: The user performing the reset
            reason: The reason for resetting the warranty
            keep_customer: Whether to keep the customer association (default: False)
        
        Returns:
            True if successful
        """
        if self.status == 'not_registered':
            raise ValidationError("Warranty is already in not_registered state.")
        
        # Log the warranty reset (keeps history via WarrantyLog)
        old_status = self.status
        old_customer = self.customer
        
        # Reset warranty fields
        self.status = 'not_registered'
        self.registered_at = None
        if not keep_customer:
            self.customer = None
        
        # Optionally adjust expiration date based on your business rules
        # For example, you might want to reset to default warranty period:
        self.extended_period = 0
        self.is_extended = False
        self.warranty_expiration_date = self.purchase_date + timedelta(days=30 * self.warranty_period)
        
        self.save()
        
        # Log the reset action
        self.logs.create(
            action='reset', 
            performed_by=user,
            details=(
                f"Warranty reset from '{old_status}' to 'not_registered'. "
                f"Previous customer: {old_customer}. "
                f"Reason: {reason or 'Not specified'}"
            )
        )
        
        return True

    def reset_due_to_return(self, user=None, return_reason=None):
        """Reset warranty due to product return"""
        return self.reset_warranty(
            user=user, 
            reason=f"Product returned. {return_reason or ''}"
        )

    def reset_due_to_exchange(self, user=None, exchange_order=None):
        """Reset warranty due to product exchange"""
        return self.reset_warranty(
            user=user, 
            reason=f"Product exchanged. New order: {exchange_order.order_number if exchange_order else 'N/A'}"
        )

    def reset_for_resale(self, user=None):
        """Reset warranty for product resale"""
        return self.reset_warranty(
            user=user, 
            reason="Product prepared for resale"
        )

    def save(self, *args, **kwargs):
        """
        Overrides the default save method of Django's models.Model.
        Automatically sets expiration date, registration details, and validates relationships.
        """
        self.clean()  # Run validation checks
        
        if not self.purchase_date:
            raise ValidationError("Purchase date must be set before saving the warranty.")
        if not self.warranty_expiration_date:
            self.warranty_expiration_date = self.purchase_date + timedelta(days=30 * (self.warranty_period + self.extended_period))
        if self.status == 'active' and not self.registered_at:
            self.registered_at = now()
        
        # Don't create logs here, let transition_status handle it
        super().save(*args, **kwargs)

    def clean(self):
        """
        Validate warranty data integrity.
        Ensures that customer, order, and product_unit are properly related.
        """
        super().clean()
        
        # Add null check for metadata field
        if hasattr(self, 'metadata'):
            if self.metadata is None:
                self.metadata = {}
                
            # Process metadata items if needed
            for key, value in self.metadata.items():
                # Process metadata items as needed
                pass
        
        if self.order and self.product_unit:
            # If order and product_unit are specified, ensure the product_unit belongs to this order
            # Find if this product_unit is assigned to any item in this order
            product_assigned_to_order = any(
                self.product_unit in item.assigned_units_relation.all()
                for item in self.order.items.all()
            )
            
            if not product_assigned_to_order:
                raise ValidationError({
                    'product_unit': f"This product unit ({self.product_unit}) is not assigned to the specified order ({self.order})"
                })
        
        if self.product_unit and hasattr(self.product_unit, 'product') and hasattr(self, 'order') and self.order:
            # Validate product integrity - ensure the serial number belongs to the correct product
            for item in self.order.items.all():
                if self.product_unit in item.assigned_units_relation.all():
                    # Found the product unit in the order items
                    if item.product != self.product_unit.product:
                        raise ValidationError({
                            'product_unit': f"This product unit's product ({self.product_unit.product}) doesn't match "
                                           f"the order item's product ({item.product})"
                        })
                    break

    def __str__(self):
        return f"Warranty for {self.product_unit.serial_number}" if self.product_unit else "Warranty for unknown product unit"

class WarrantyLog(models.Model):
    """
    Represents a log entry for a warranty status change.
    """
    warranty = models.ForeignKey(Warranty, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(
        max_length=20, 
        choices=[
            ('not_registered', 'Not Registered'),
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('void', 'Void'),
            ('extended', 'Extended'),
            ('reset', 'Reset'),
            ('created', 'Created'),
            ('admin_edit', 'Admin Edit'),  # Add this line
        ]
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    details = models.TextField(null=True, blank=True)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Warranty Log"
        verbose_name_plural = "Warranty Logs"
        ordering = ['-performed_at']

    def __str__(self):
        return f"{self.warranty} - {self.action}"

    def get_action_display(self):
        """Return the human-readable name of the action."""
        return dict(Warranty._meta.get_field('status').choices)[self.action]

