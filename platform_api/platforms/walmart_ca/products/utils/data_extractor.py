"""Utilities for extracting specific data from Walmart CA product responses"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class DataExtractor:
    """Extract and format data from API responses"""
    
    @staticmethod
    def extract_product_type(data: Dict) -> str:
        """
        Extract product type using established priority:
        1. Direct productType field
        2. productType from attributes 
        3. Category name
        4. "Unknown" fallback
        """
        if data.get("productType"):
            return data["productType"]
        
        if "attributes" in data and data.get("attributes", {}).get("productType"):
            return data["attributes"]["productType"]
            
        if "category_data" in data and data["category_data"].get("category"):
            return data["category_data"]["category"]
            
        return "Unknown"
    
    @staticmethod
    def extract_category_data(data: Dict) -> Dict[str, Any]:
        """Extract category information from product data"""
        category_data = {
            "category": None,
            "subcategory": None, 
            "category_path": []
        }
        
        try:
            if "categoryPath" in data:
                category_data["category_path"] = data["categoryPath"]
                if len(category_data["category_path"]) > 0:
                    category_data["category"] = category_data["category_path"][0]
                if len(category_data["category_path"]) > 1:
                    category_data["subcategory"] = category_data["category_path"][1]
        except Exception as e:
            logger.warning(f"Error extracting category data: {str(e)}")
            
        return category_data
    
    @staticmethod
    def extract_images(data: Dict) -> List[Dict[str, str]]:
        """Extract image URLs and types from product data"""
        images = []
        
        try:
            # Extract from images array if present
            if "images" in data and isinstance(data["images"], list):
                for img in data["images"]:
                    if isinstance(img, dict) and "url" in img:
                        images.append({
                            "url": img["url"],
                            "type": img.get("type", "PRIMARY")
                        })
            
            # Also check for primaryImageUrl 
            if "primaryImageUrl" in data and data["primaryImageUrl"]:
                # Only add if not already present
                if not any(img.get("url") == data["primaryImageUrl"] for img in images):
                    images.append({
                        "url": data["primaryImageUrl"],
                        "type": "PRIMARY" 
                    })
        except Exception as e:
            logger.warning(f"Error extracting image data: {str(e)}")
            
        return images
    
    @staticmethod
    def extract_variant_data(data: Dict) -> Dict[str, Any]:
        """Enhanced variant information extraction"""
        variant_data = {
            "is_variant": False,
            "variant_group_id": None,
            "variant_attributes": []
        }
        
        try:
            # Check direct variants object first (common in platform_data)
            if "variants" in data and isinstance(data["variants"], dict):
                variant_data["is_variant"] = data["variants"].get("is_variant", False)
                variant_data["variant_group_id"] = data["variants"].get("variant_group_id")
                variant_data["variant_attributes"] = data["variants"].get("variant_attributes", [])
                return variant_data
                
            # Legacy path for variantGroupInfo
            if "variantGroupInfo" in data and isinstance(data["variantGroupInfo"], dict):
                variant_info = data["variantGroupInfo"]
                # Mark as a variant if the product is not primary
                variant_data["is_variant"] = not variant_info.get("isPrimary", True)
                variant_data["variant_group_id"] = variant_info.get("variantGroupId")
                
                # Extract variant attributes from groupingAttributes if present
                if "groupingAttributes" in variant_info and isinstance(variant_info["groupingAttributes"], list):
                    variant_data["variant_attributes"] = variant_info["groupingAttributes"]
        except Exception as e:
            logger.warning(f"Error extracting variant data: {str(e)}")
            
        return variant_data
    
    @staticmethod
    def extract_price_data(data: Dict) -> Dict[str, Any]:
        """Extract price information with better fallback handling"""
        price_data = {
            "price": None,
            "currency": "CAD",  # Default to CAD for Walmart CA
        }
        
        try:
            # Try to get from price object first
            if "price" in data and isinstance(data["price"], dict):
                price_info = data["price"]
                if "amount" in price_info:
                    price_data["price"] = float(price_info["amount"])
                if "currency" in price_info:
                    price_data["currency"] = price_info["currency"]
            
            # Try direct price value
            elif "price" in data and data["price"]:
                price_data["price"] = float(data["price"])
            
            # Try to get from order item charges
            elif "charges" in data and isinstance(data["charges"], list):
                for charge in data["charges"]:
                    if charge.get("chargeType") == "PRODUCT" and charge.get("amount"):
                        price_data["price"] = float(charge["amount"])
                        if charge.get("currency"):
                            price_data["currency"] = charge["currency"]
                        break
        except Exception as e:
            logger.warning(f"Error extracting price data: {str(e)}")
            
        return price_data

    @staticmethod
    def extract_inventory_data(data: Dict) -> Dict[str, Any]:
        """Extract inventory information with improved status handling"""
        inventory_data = {
            "quantity": 0,
            "status": "OUT_OF_STOCK"
        }
        
        try:
            # Check for quantity in the inventory object first (more reliable)
            if "inventory" in data and isinstance(data["inventory"], dict):
                if "quantity" in data["inventory"]:
                    inventory_data["quantity"] = int(data["inventory"]["quantity"])
                if "status" in data["inventory"]:
                    inventory_data["status"] = data["inventory"]["status"]
            # Fallback to direct quantity field
            elif "quantity" in data:
                inventory_data["quantity"] = int(data["quantity"])
                
            # Set status based on quantity if not explicitly provided
            if "status" not in inventory_data or not inventory_data["status"]:
                if inventory_data["quantity"] > 0:
                    inventory_data["status"] = "IN_STOCK"
                else:
                    inventory_data["status"] = "OUT_OF_STOCK"
        except Exception as e:
            logger.warning(f"Error extracting inventory data: {str(e)}")
            
        return inventory_data

    @staticmethod
    def extract_attributes(data: Dict) -> Dict[str, Any]:
        """Extract product attributes"""
        attributes = {}
        
        try:
            if "productAttributes" in data:
                for attr in data["productAttributes"]:
                    if "name" in attr and "value" in attr:
                        attributes[attr["name"]] = attr["value"]
                        
            # Common direct attributes
            for key in ["color", "size", "gender", "material", "productType"]:
                if key in data and data[key]:
                    attributes[key] = data[key]
        except Exception as e:
            logger.warning(f"Error processing attributes: {str(e)}")
            
        return attributes