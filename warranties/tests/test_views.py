from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from products.models import Product, ProductUnit
from customers.models import Customer
from warranties.models import Warranty
import uuid
import datetime


class WarrantyViewSetTestCase(TestCase):
    """
    Test suite for WarrantyViewSet endpoints.
    """

    def get_unique_phone_number(self):
        """
        Generate a unique phone number with a fixed length.
        Ensures no duplicate phone numbers across tests.
        """
        unique_part = str(uuid.uuid4().int)[:7]  # Use first 7 digits of a UUID integer
        return f"12345{unique_part}"  # Prepend a common prefix

    def setUp(self):
        """
        Test setup to create common objects used across multiple test cases.
        """
        # Generate a unique phone number for the customer
        self.phone_number = self.get_unique_phone_number()

        # Create a Product for the ProductUnit
        self.product = Product.objects.create(
            product_name="Test Product",
            category="Test Category"
        )

        # Create a ProductUnit linked to the Product
        self.product_unit = ProductUnit.objects.create(
            serial_number="12345",
            product=self.product
        )

        # Create a Customer with the generated phone number
        self.customer = Customer.objects.create(
            name="John Doe",
            email="john.doe@example.com",
            phone_number=self.phone_number
        )

        # Create a Warranty linked to the ProductUnit and Customer
        today = datetime.date.today()
        self.warranty = Warranty.objects.create(
            product_unit=self.product_unit,
            customer=self.customer,
            purchase_date=today,
            warranty_period=3,  # Total warranty period (3 months)
            warranty_expiration_date=today + datetime.timedelta(days=90),
            status="not_registered"
        )

    def test_activate_warranty_success(self):
        """
        Test activating a warranty for a valid product unit.
        Expect: 201 Created and warranty status becomes 'active'.
        """
        unique_phone = self.get_unique_phone_number()
        data = {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "phone_number": unique_phone
        }
        url = reverse('warranty-activate', kwargs={'serial_number': self.product_unit.serial_number})
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        warranty = Warranty.objects.get(product_unit=self.product_unit)
        self.assertEqual(warranty.status, "active")
        self.assertEqual(warranty.customer.phone_number, unique_phone)


    def test_activate_warranty_already_active(self):
        """
        Test activating a warranty that is already 'active'.
        Expect: 200 OK with a redirect response.
        """
        self.warranty.status = "active"
        self.warranty.save()

        data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone_number": self.customer.phone_number
        }
        url = reverse('warranty-activate', kwargs={'serial_number': self.product_unit.serial_number})
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("redirect", response.data)



    def test_activate_warranty_expired(self):
        """
        Test activating an expired warranty.
        Expect: 400 Bad Request with an error message.
        """
        self.warranty.status = "expired"
        self.warranty.save()

        data = {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "phone_number": self.get_unique_phone_number()
        }
        url = reverse('warranty-activate', kwargs={'serial_number': self.product_unit.serial_number})
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_activate_warranty_success(self):
        """
        Test activating a warranty for a valid product unit.
        Expect: 201 Created and warranty status becomes 'active'.
        """
        unique_phone = self.get_unique_phone_number()
        data = {
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "phone_number": unique_phone
        }
        url = reverse('warranty-activate', kwargs={'serial_number': self.product_unit.serial_number})
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        warranty = Warranty.objects.get(product_unit=self.product_unit)
        self.assertEqual(warranty.status, "active")
        self.assertEqual(warranty.customer.phone_number, unique_phone)


    def test_activate_warranty_invalid_serial(self):
        """
        Test activating a warranty with an invalid serial number.
        Expect: 404 Not Found.
        """
        data = {
            "name": "Invalid User",
            "email": "invalid@example.com",
            "phone_number": self.get_unique_phone_number()
        }
        url = reverse('warranty-activate', kwargs={'serial_number': 'invalid123'})
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)


    def test_activate_warranty_duplicate_customer(self):
        """
        Test activating a warranty for an existing customer.
        Expect: 201 Created and no duplicate customer record.
        """
        data = {
            "name": "John Doe",
            "email": "updated.john.doe@example.com",  # Updated email
            "phone_number": self.customer.phone_number
        }
        url = reverse('warranty-activate', kwargs={'serial_number': self.product_unit.serial_number})
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Customer.objects.filter(phone_number=self.customer.phone_number).count(), 1)
        self.assertEqual(Customer.objects.get(phone_number=self.customer.phone_number).email, "updated.john.doe@example.com")


    def test_warranty_status_invalid_serial(self):
        """
        Test fetching warranty status with an invalid serial number.
        Expect: 404 Not Found.
        """
        url = reverse('warranty-status', kwargs={'serial_number': 'invalid123'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("detail", response.data)
