from django.db import models, transaction
from django.utils.timezone import now
from datetime import timedelta

from django.core.exceptions import ValidationError


# def generate_activation_code(length=4):
#     """
#     Generate a simple 4-character alphanumeric activation code.
#     """

#     return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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
    # activation_code = models.CharField(max_length=4, null=True, blank=True)

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
    def transition_status(self, new_status):
        """
        Change the warranty status if the transition is valid.
        """
        if not self.can_transition_to(new_status):
            raise ValidationError(f"Invalid status transition from {self.status} to {new_status}")
        self.status = new_status
        if new_status == 'active' and not self.registered_at:
            self.registered_at = now()
        self.save()

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
        
    # activation_code_cache = None

    def save(self, *args, **kwargs):
        """
        Overrides the default save method of Django's models.Model.
        Automatically sets expiration date, registration details, and generates an activation code if not already set.
        """

        if not self.purchase_date:
            raise ValidationError("Purchase date must be set before saving the warranty.")
        if not self.warranty_expiration_date:
            self.warranty_expiration_date = self.purchase_date + timedelta(days=30 * (self.warranty_period + self.extended_period))
        if self.status == 'active' and not self.registered_at:
            self.registered_at = now()
        # if not self.activation_code:  # Generate only if not already set
        #     if not Warranty.activation_code_cache:
        #         Warranty.activation_code_cache = generate_activation_code()
            # self.activation_code = Warranty.activation_code_cache
        super().save(*args, **kwargs)


    def __str__(self):
        return f"Warranty for {self.product_unit.serial_number}" if self.product_unit else "Warranty for unknown product unit"
        return "Warranty for unknown product unit"
   
