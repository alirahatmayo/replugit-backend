# processor/platforms/walmart_ca/product.py
from typing import Dict, Any
from platform_api.processors.base.product import BaseProductProcessor
import re
import json
import logging
from datetime import datetime
from products.models import Product
logger = logging.getLogger(__name__)

class WalmartCAProductProcessor(BaseProductProcessor):
    """Walmart CA specific product processor"""

    def extract_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product data from Walmart CA format"""
        # Use fallback value 'Unknown Product' if neither productName nor name is provided.

        name = product_data.get('name') 
        sku = product_data.get('sku') 
        gtin = product_data.get('gtin')
        upc = product_data.get('upc')
        product_type = product_data.get('product_type') or product_data.get('productType', 'Unknown 1')
        description = product_data.get('description', '')

        # Extract variant information
        variant_info = self._extract_variant_data(product_data)

        # Build detailed platform data with the original API response.
        platform_data = {
            'walmart_ca': {
                'wpid': product_data.get('wpid', ''),
                'price': product_data.get('price', {}),
                'currency': product_data.get('currency', {}),
                'publishedStatus': product_data.get('published_status', ''),
                'lifecycleStatus': product_data.get('lifecycle_status', ''),
                'shelf': product_data.get('shelf', ''),
                'productType': product_data.get('product_type', ''),
                'variants': variant_info  # Add variant information here
                            }
        }
        # Handle price field: if it's a dict, extract amount and currency; otherwise assume it's a direct value.
        price_info = product_data.get('price', {})
        if isinstance(price_info, dict):
            price = price_info.get('amount')
            currency = price_info.get('currency')
        else:
            price = price_info  # directly assigned numeric value
            currency = None

        published_status = product_data.get('publishedStatus')
        lifecycle_status = product_data.get('lifecycleStatus')
        shelf = product_data.get('shelf')  # Might be a JSON string. Parse if needed.
        last_updated = product_data.get('last_updated') or datetime.now().isoformat()
        
        # Log the raw response and key mappings for debugging
        logger.debug(f"Raw product response: {json.dumps(product_data, indent=2)}")
        print(f"Extracting product data for {name} ({platform_data['walmart_ca']['wpid']})")
        # print(f"Platform data: {platform_data}")
        
        # Return the mapped product data dictionary
        return {
            'sku': sku,
            'name': name,
            'platform': 'walmart_ca',
            'gtin': gtin,
            'product_type': product_type,
            'description': description,
            'platform_data': platform_data,
            'upc': upc,
            'price': price,
            'currency': currency,
            'published_status': published_status,
            'lifecycle_status': lifecycle_status,
            'shelf': shelf,
            'last_updated': last_updated,
        }

    def extract_specifications(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specifications from product data"""
        # Return empty dict for now - we'll implement specific product specs later
        return {}

    def _extract_variant_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract variant-related information from product data"""
        variant_info = {
            'variantGroupId': product_data.get('variantGroupId'),
            'isPrimary': product_data.get('variantGroupInfo', {}).get('isPrimary', False),
            'attributes': product_data.get('variantGroupInfo', {}).get('groupingAttributes', []),
            'variations': []  # This could be populated if you fetch variations separately
        }

        # Clean up the dictionary by removing None values
        return {k: v for k, v in variant_info.items() if v is not None}

    def process_additional_data(self, product: Product, raw_data: Dict[str, Any]) -> None:
        """Process additional product data including variants"""
        super().process_additional_data(product, raw_data)
        
        # If the product has a variant group ID, fetch and process variations
        variant_group_id = raw_data.get('variantGroupId')
        if variant_group_id:
            try:
                # This would require implementing fetch_variations in your API client
                variations = self.platform.fetch_variations(product.sku)
                
                # Update platform_data with variations
                platform_data = product.platform_data.get('walmart_ca', {})
                platform_data['variants']['variations'] = variations
                
                # Save the updated product
                product.save()
                
            except Exception as e:
                logger.error(f"Error processing variations for {product.sku}: {e}")