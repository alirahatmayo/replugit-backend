from django.db import models
from django.forms import ValidationError

class Customer(models.Model):
    """
    Represents a customer in the system.
    Supports multiple contact methods and platform tracking.
    """
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    relay_email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    source_platform = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=[
            ('walmart_ca', 'Walmart Canada'),
            ('walmart_us', 'Walmart US'),
            ('amazon', 'Amazon'),
            ('shopify', 'Shopify'),
            ('bestbuy', 'BestBuy'),
            ('manual', 'Manual Entry'),
        ],
        help_text="Platform where the customer was first added."
    )
    tags = models.JSONField(null=True, blank=True)  # Metadata or categorization
    address = models.JSONField(null=True, blank=True, help_text="Address details from platform orders.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Ensure at least one identifier (email, relay_email, or phone_number) exists.
        Validate the structure of the address field if provided.
        """
        if not (self.email or self.relay_email or self.phone_number):
            raise ValidationError("At least one contact field (email, relay_email, or phone_number) must be provided.")

        if self.address:
            required_keys = {'name', 'address1', 'city', 'state', 'postalCode', 'country'}
            missing_keys = required_keys - self.address.keys()
            if missing_keys:
                raise ValidationError(f"Address is missing required fields: {', '.join(missing_keys)}")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.email or self.relay_email or "Unnamed Customer"

class CustomerChangeLog(models.Model):
    """
    Tracks changes to customer details, such as phone number or email.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='update_history')
    field_name = models.CharField(max_length=50)  # e.g., 'phone_number', 'email', 'name'
    old_value = models.CharField(max_length=100, null=True, blank=True)
    new_value = models.CharField(max_length=100,  null=True, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer} - {self.field_name} updated on {self.updated_at}"
