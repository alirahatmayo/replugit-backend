from models import Customer
from django.db import transaction


def merge_customers(primary_customer, duplicate_customer):
    """
    Merge duplicate customer data into a primary customer.

    Args:
        primary_customer: The Customer instance to retain.
        duplicate_customer: The Customer instance to merge and delete.

    Returns:
        Customer: The updated primary customer.
    """
    with transaction.atomic():
        # Merge fields if primary fields are empty
        for field in ['email', 'relay_email', 'phone_number']:
            primary_value = getattr(primary_customer, field, None)
            duplicate_value = getattr(duplicate_customer, field, None)
            if not primary_value and duplicate_value:
                setattr(primary_customer, field, duplicate_value)

        # Save the updated primary customer
        primary_customer.save()

        # Transfer relationships, if applicable (e.g., orders, warranties)
        duplicate_customer.orders.all().update(customer=primary_customer)
        duplicate_customer.warranties.all().update(customer=primary_customer)

        # Delete the duplicate customer
        duplicate_customer.delete()

        return primary_customer
