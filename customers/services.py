from .models import Customer  # Fix import
from django.db import models
import logging

logger = logging.getLogger(__name__)

class CustomerService:
    @staticmethod
    def get_or_create_customer(name: str, email: str, phone_number: str) -> Customer:
        """
        Retrieve an existing customer by phone or email, or create a new one.
        
        Args:
            name (str): Customer's name
            email (str): Customer's email
            phone_number (str): Customer's phone number
            source_platform (str, optional): Source of the customer. Defaults to "manual".
        
        Returns:
            Customer: The found or created customer object
        """
        customer = Customer.objects.filter(models.Q(phone_number=phone_number) | models.Q(email=email)).first()
        if not customer:
            try:
                customer = Customer.objects.create(
                    name=name,
                    email=email,
                    phone_number=phone_number,
                )
            except Exception as e:
                logger.error(f"Failed to create customer: {e}")
                raise
        return customer