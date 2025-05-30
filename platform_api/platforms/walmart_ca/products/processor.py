from typing import Dict, Any, Optional, List, Tuple
import logging
from decimal import Decimal
from products.models import Product
from .utils.json_serializer import JsonSerializer
from .utils.data_extractor import DataExtractor
from .utils.format_helper import FormatHelper

logger = logging.getLogger(__name__)

class WalmartCAProductProcessor:
    """Processes Walmart CA product data into standardized format"""
    
    def process_product(self, data: Dict) -> Optional[Dict[str, Any]]:
        """Process a single product from Walmart CA API"""
        if not data:
            logger.warning("Empty product data received")
            return None
            
        try:
            # Extract basic product information
            product = {
                "sku": data.get("sku"),
                "wpid": data.get("wpid"),
                "gtin": data.get("gtin"),
                "product_name": FormatHelper.clean_product_name(data.get("productName")),
                "brand": data.get("brand"),
                "shelf": data.get("shelf"),
                "product_type": DataExtractor.extract_product_type(data),
                "platform": "walmart_ca",
                "status": {
                    "published": data.get("publishedStatus"),
                    "lifecycle": data.get("lifecycleStatus")
                },
                # Use DataExtractor methods for all data extraction
                "price_data": DataExtractor.extract_price_data(data),
                "inventory": DataExtractor.extract_inventory_data(data),
                "category_data": DataExtractor.extract_category_data(data),
                "images": DataExtractor.extract_images(data),
                "attributes": DataExtractor.extract_attributes(data),
                "variants": DataExtractor.extract_variant_data(data),
                
                # Add raw platform-specific fields directly
                "raw_data": {
                    "wpid": data.get("wpid"),
                    "variantGroupId": data.get("variantGroupId"),
                    "shelf_sku": data.get("sellerSku"),
                    "lifecycleStatus": data.get("lifecycleStatus"),
                    "publishedStatus": data.get("publishedStatus")
                }
            }
            
            # Check if we have minimum required fields
            if not product["sku"]:
                logger.warning("Product missing required SKU field")
                return None
                
            return product
            
        except Exception as e:
            logger.error(f"Error processing product {data.get('sku', 'unknown')}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
  
        
    # def _process_inventory(self, data: Dict) -> Dict[str, Any]:
    #     """Extract inventory information"""
    #     inventory_data = {
    #         "quantity": 0,
    #         "status": "OUT_OF_STOCK"
    #     }
        
    #     try:
    #         if "quantity" in data:
    #             inventory_data["quantity"] = int(data["quantity"])
    #             if inventory_data["quantity"] > 0:
    #                 inventory_data["status"] = "IN_STOCK"
    #     except:
    #         pass
            
    #     return inventory_data
    
    # def _process_category(self, data: Dict) -> Dict[str, Any]:
    #     """Extract category information"""
    #     category_data = {
    #         "category": None,
    #         "subcategory": None,
    #         "category_path": []
    #     }
        
    #     try:
    #         if "categoryPath" in data:
    #             category_data["category_path"] = data["categoryPath"]
    #             if len(category_data["category_path"]) > 0:
    #                 category_data["category"] = category_data["category_path"][0]
    #             if len(category_data["category_path"]) > 1:
    #                 category_data["subcategory"] = category_data["category_path"][1]
    #     except:
    #         pass
            
    #     return category_data
    
    # def _process_images(self, data: Dict) -> List[Dict[str, str]]:
    #     """Extract image information"""
    #     images = []
        
    #     try:
    #         if "images" in data and isinstance(data["images"], list):
    #             for img in data["images"]:
    #                 if isinstance(img, dict) and "url" in img:
    #                     images.append({
    #                         "url": img["url"],
    #                         "type": img.get("type", "PRIMARY")
    #                     })
                        
    #         # Check for primaryImageUrl field
    #         if "primaryImageUrl" in data and data["primaryImageUrl"]:
    #             if not any(img.get("url") == data["primaryImageUrl"] for img in images):
    #                 images.append({
    #                     "url": data["primaryImageUrl"],
    #                     "type": "PRIMARY"
    #                 })
    #     except:
    #         pass
            
    #     return images
    
    # def _process_attributes(self, data: Dict) -> Dict[str, Any]:
    #     """Extract product attributes"""
    #     attributes = {}
        
    #     try:
    #         if "productAttributes" in data:
    #             for attr in data["productAttributes"]:
    #                 if "name" in attr and "value" in attr:
    #                     attributes[attr["name"]] = attr["value"]
                        
    #         # Common direct attributes
    #         for key in ["color", "size", "gender", "material", "productType"]:  # Added productType here
    #             if key in data and data[key]:
    #                 attributes[key] = data[key]
    #     except Exception as e:
    #         logger.warning(f"Error processing attributes: {e}")
            
    #     return attributes
    
    # def _process_variants(self, data: Dict) -> Dict[str, Any]:
    #     """Extract variant information"""
    #     variant_data = {
    #         "is_variant": False,
    #         "variant_group_id": None,
    #         "variant_attributes": []
    #     }
        
    #     try:
    #         if "variantGroupId" in data and data["variantGroupId"]:
    #             variant_data["is_variant"] = True
    #             variant_data["variant_group_id"] = data["variantGroupId"]
                
    #         if "variantAttributeNames" in data:
    #             variant_data["variant_attributes"] = data["variantAttributeNames"]
    #     except:
    #         pass
            
    #     return variant_data

    # def _convert_decimal_to_string(self, data):
    #     """Recursively convert Decimal values to strings for JSON serialization"""
    #     if isinstance(data, Decimal):
    #         return str(data)
    #     elif isinstance(data, dict):
    #         return {k: self._convert_decimal_to_string(v) for k, v in data.items()}
    #     elif isinstance(data, list):
    #         return [self._convert_decimal_to_string(i) for k, v in data.items()]
    #     else:
    #         return data

    def save_product(self, product_data: Dict) -> Tuple[Product, bool]:
        """Save a processed product to the database"""
        if not product_data or not product_data.get('sku'):
            logger.warning("Cannot save product without SKU")
            return None, False
            
        sku = product_data.get('sku')
        created = False
        
        try:
            # Try to find existing product by SKU
            try:
                product = Product.objects.get(sku=sku)
                logger.info(f"Found existing product {sku}, updating")
            except Product.DoesNotExist:
                product = Product(sku=sku)
                created = True
                logger.info(f"Creating new product {sku}")
                
            # Update product fields
            product.name = product_data.get('product_name', '')
            
            # Make sure to save GTIN
            if product_data.get('gtin'):
                product.gtin = product_data.get('gtin')
            
            # Product type priority:
            # 1. Use direct product_type field if present
            # 2. Look for productType in attributes
            # 3. Use category from category_data
            # 4. Fallback to existing value or "Unknown"
            product_type = DataExtractor.extract_product_type(product_data)
            
            product.product_type = product_type
            
            # Handle description
            if 'attributes' in product_data and 'description' in product_data['attributes']:
                product.description = product_data['attributes']['description']
            
            # Update platform information
            product.platform = 'walmart_ca'
            
            # Create platform-specific data structure
            walmart_data = {
                'wpid': product_data.get('wpid'),
                'gtin': product_data.get('gtin'),
                'variants': product_data.get('variants'),
                'status': product_data.get('status'),
                'shelf': product_data.get('shelf'),
                'variant_group_id': product_data.get('variants', {}).get('variant_group_id'),
                'attributes': product_data.get('attributes'),
                'category_info': product_data.get('category_data'),
                'inventory': product_data.get('inventory'),
                'images': product_data.get('images')
                # Note: price_data is removed from here as we'll store it separately
            }            
            
            # Get existing platform_data or create empty dict
            try:
                platform_data = getattr(product, 'platform_data', {}) or {}
                if platform_data is None:
                    platform_data = {}
            except (AttributeError, TypeError):
                platform_data = {}
            
            # IMPORTANT: Convert Decimal objects to strings before saving to JSON field
            json_safe_data = JsonSerializer.convert_for_json(walmart_data)
            
            # Update the Walmart CA portion
            platform_data['walmart_ca'] = json_safe_data
            
            # Save platform_data to product
            product.platform_data = platform_data
            
            # ----- HANDLE PRICE DATA SEPARATELY -----
            
            # Get existing prices or create empty dict
            try:
                price = getattr(product, 'price_data', {}) or {}
                if price is None:
                    price = {}
            except (AttributeError, TypeError):
                price = {}
                
            # Extract price data and ensure it's JSON serializable
            price_data = product_data.get('price_data', {})
            json_safe_price_data = JsonSerializer.convert_for_json(price_data)
            
            # Store with platform as key
            price['walmart_ca'] = json_safe_price_data
            
            # Save price data to product
            product.price_data = price
            
            # Add debug logging before save
            logger.debug(f"Saving product {sku} with fields: {product.__dict__}")
            
            # Save the product
            product.save()
            logger.info(f"Successfully saved product {sku}")
            
            return product, created
            
        except Exception as e:
            logger.error(f"Error saving product {sku}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, False
    
    def save_products(self, products: List[Dict]) -> Dict[str, int]:
        """
        Save multiple products to the database
        
        Args:
            products: List of processed product data from process_product()
            
        Returns:
            Statistics dictionary with counts
        """
        stats = {
            'total': len(products),
            'created': 0,
            'updated': 0,
            'error': 0
        }
        
        for product_data in products:
            try:
                product, created = self.save_product(product_data)
                if product:
                    if created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1
                else:
                    stats['error'] += 1
            except Exception:
                stats['error'] += 1
                
        return stats