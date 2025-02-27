#processors/base/product.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from products.models import Product
import logging
from django.db import transaction
from decimal import Decimal

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
        """
        Extract product data from raw data.

        Args:
            product_data (Dict[str, Any]): Raw product data.

        Returns:
            Dict[str, Any]: Extracted product data with keys such as 'sku', 'name', 'platform', 
                            'gtin', 'product_type', 'description', 'platform_data', etc.
        """
        pass

    def create_or_update_product(self, product_data: Dict[str, Any]) -> Product:
        """Create or update product record using prepared defaults"""
        # Use prepare_product_defaults to get the defaults dictionary.
        defaults = self.prepare_product_defaults(product_data)
        print(f"Defaults: {defaults}")

        product, created = Product.objects.update_or_create(
            sku=product_data.get('sku'),
            platform=product_data.get('platform'),
            defaults=defaults
        )
        if created:
            logger.info(f"Created new product: {product.sku}")
        else:
            logger.info(f"Updated existing product: {product.sku}")

        return product

    def validate_product_data(self, product_data: Dict[str, Any]) -> None:
        """Validate required product fields"""
        required_fields = ['sku', 'name', 'platform']
        missing = [f for f in required_fields if f not in product_data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

    def validate_processed_data(self, processed_data: Dict[str, Any]) -> None:
        """Validate processed data before saving"""
        required_fields = ['sku', 'name', 'platform', 'specifications']
        missing = [f for f in required_fields if f not in processed_data]
        if missing:
            raise ValueError(f"Missing processed fields: {', '.join(missing)}")

    def prepare_product_defaults(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare product data for database update based on the fields defined in the Product model."""
        defaults = {
            # Required field(s)
            'name': product_data['name'],
            # Model fields currently mapped
            'gtin': product_data.get('gtin'),
            'sku': product_data.get('sku'),
            'platform': product_data.get('platform'),
            'product_type': product_data.get('product_type', 'Un Recognized'),
            'description': product_data.get('description', ''),
            # Platform-specific data: allow both keys so that if one isn't present, the other is used.
            'platform_data': product_data.get('platform_data') or product_data.get('platform_specific_data', {}),
            # Additional fields from the API response
        }
        
        # Handle price: if available, convert to Decimal.
        if 'price' in product_data:
            defaults['price'] = Decimal(str(product_data['price']))
            
        return defaults

    def process_additional_data(self, product: Product, raw_data: Dict[str, Any]) -> None:
        """Process additional product data like images, variants etc."""
        # Override this method in platform-specific processors if needed
        pass

    def clean_product_name(self, name: str) -> str:
        """Clean product name by removing unnecessary text"""
        # Basic cleaning - override in platform-specific processors
        return name.strip()

    @abstractmethod
    def extract_specifications(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product specifications"""
        pass