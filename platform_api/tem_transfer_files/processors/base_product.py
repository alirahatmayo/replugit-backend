from abc import ABC, abstractmethod
from typing import Dict, Any
from products.models import Product
import logging
from django.db import transaction

logger = logging.getLogger(__name__)

class BaseProductProcessor(ABC):
    """Base class for platform-specific product processors"""

    @transaction.atomic
    def process_product(self, product_data: Dict[str, Any]) -> Product:
        """Template method to process a product"""
        try:
            # Validate product data
            self.validate_product_data(product_data)
            
            # Extract and process product
            processed_data = self.extract_product_data(product_data)
            product = self.create_or_update_product(processed_data)
            
            return product

        except Exception as e:
            logger.error(f"Error processing product: {e}", exc_info=True)
            raise

    @abstractmethod
    def extract_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product data from raw data"""
        pass

    def create_or_update_product(self, product_data: Dict[str, Any]) -> Product:
        """Create or update product record"""
        product, created = Product.objects.update_or_create(
            sku=product_data['sku'],
            platform=product_data['platform'],
            defaults=product_data
        )
        return product

    def validate_product_data(self, product_data: Dict[str, Any]) -> None:
        """Validate required product fields"""
        required_fields = ['sku', 'name']
        missing = [f for f in required_fields if f not in product_data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")