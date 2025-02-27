from django.test import TestCase
from platform_api.processors.base.product import BaseProductProcessor
from products.models import Product
from typing import Dict, Any

class TestProcessor(BaseProductProcessor):
    """Test implementation of BaseProductProcessor"""
    def extract_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'sku': product_data['sku'],
            'name': product_data['name'],
            'platform': 'walmart_ca',
            'product_type': 'Test Type',
            'description': 'Test Description',
            'platform_data': {'walmart_ca': {'wpid': 'test123'}}
        }

class BaseProductProcessorTest(TestCase):
    def setUp(self):
        self.processor = TestProcessor()
        self.valid_data = {
            'sku': 'TEST123',
            'name': 'Test Product',
            'platform': 'walmart_ca'
        }

    def test_validate_product_data(self):
        # Test valid data
        self.processor.validate_product_data(self.valid_data)
        
        # Test missing required fields
        invalid_data = {'sku': 'TEST123'}
        with self.assertRaises(ValueError):
            self.processor.validate_product_data(invalid_data)

    def test_process_product(self):
        product = self.processor.process_product(self.valid_data)
        self.assertEqual(product.sku, 'TEST123')
        self.assertEqual(product.name, 'Test Product')
        self.assertEqual(product.platform, 'walmart_ca')
        self.assertEqual(product.product_type, 'Test Type')
        self.assertIn('walmart_ca', product.platform_data)