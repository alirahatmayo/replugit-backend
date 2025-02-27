from django.forms import ValidationError
from django.test import TestCase
from .models import Product, ProductUnit

class ProductUnitTestCase(TestCase):
    """Test cases for ProductUnit model"""
    
    def setUp(self):
        self.product = Product.objects.create(product_name="Laptop", category="Electronics")
        self.product_unit = ProductUnit.objects.create(product=self.product, serial_number="SN12345", status="in_stock")

    def test_product_unit_valid_status(self):
        """Test valid status transition with assigned order"""
        self.product_unit.status = 'sold'
        self.product_unit.assigned_to_order = True
        self.product_unit.save()

    def test_invalid_status_transition(self):
        """Test invalid status transition without order assignment"""
        self.product_unit.status = 'sold'
        self.product_unit.assigned_to_order = False
        with self.assertRaises(ValidationError):
            self.product_unit.save()

    def test_assigned_status_requires_serial(self):
        """Test that assigned status requires a serial number"""
        self.product_unit.serial_number = None
        self.product_unit.status = 'assigned'
        with self.assertRaises(ValidationError):
            self.product_unit.save()

    def test_valid_in_stock_status(self):
        """Test in_stock status is always valid"""
        self.product_unit.status = 'in_stock'
        self.product_unit.assigned_to_order = False
        self.product_unit.save()
        self.assertEqual(self.product_unit.status, 'in_stock')
