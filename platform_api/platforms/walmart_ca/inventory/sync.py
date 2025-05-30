from typing import Dict, List, Optional, Any
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def sync_inventory(
    api,
    sku: str
) -> Dict[str, Any]:
    """
    Sync inventory for a specific product from Walmart CA
    
    Args:
        api: WalmartCA API client
        sku: Product SKU to sync
        
    Returns:
        Status of sync operation
    """
    if not sku:
        return {"success": False, "message": "No SKU provided"}
        
    # Remove CA- prefix if needed
    if sku.startswith("CA-"):
        api_sku = sku[3:]
    else:
        api_sku = sku
    
    try:
        # First fetch product from Walmart CA
        logger.info(f"Fetching inventory status for {sku} from Walmart CA")
        response = api.make_request('GET', f'items/{api_sku}')
        
        if not response:
            return {"success": False, "message": "No response from API"}
            
        # Extract inventory data
        if 'availability' in response:
            availability = response.get('availability', {})
            status = availability.get('availabilityStatus', 'OUT_OF_STOCK')
            quantity = int(availability.get('quantity', 0))
            
            # Update local inventory
            try:
                from inventory.models import Inventory, Location, InventoryHistory
                from products.models import Product
                
                # Get product
                product_sku = sku if sku.startswith("CA-") else f"CA-{sku}"
                product = Product.objects.get(sku=product_sku)
                
                # Get location
                location, _ = Location.objects.get_or_create(
                    code='WALMART_CA',
                    defaults={'name': 'Walmart CA'}
                )
                
                # Get or create inventory record
                inventory, created = Inventory.objects.get_or_create(
                    product=product,
                    platform='walmart_ca',
                    location=location,
                    defaults={'quantity': 0}
                )
                
                # Record previous qty
                previous_qty = inventory.quantity
                
                # Update inventory
                inventory.quantity = quantity
                inventory.status = 'IN_STOCK' if status == 'AVAILABLE' else 'OUT_OF_STOCK'
                inventory.last_sync = datetime.now()
                inventory.save()
                
                # Create history record if quantity changed
                if quantity != previous_qty:
                    InventoryHistory.objects.create(
                        inventory=inventory,
                        previous_quantity=previous_qty,
                        new_quantity=quantity,
                        change=quantity - previous_qty,
                        reason='SYNC',
                        reference=f"API Sync {datetime.now().strftime('%Y-%m-%d')}"
                    )
                
                return {
                    "success": True,
                    "product": product_sku,
                    "platform_quantity": quantity,
                    "previous_quantity": previous_qty,
                    "current_quantity": inventory.quantity,
                    "status": inventory.status
                }
                
            except Product.DoesNotExist:
                return {"success": False, "message": f"Product not found for SKU: {product_sku}"}
            except Exception as e:
                logger.error(f"Error updating local inventory: {e}")
                return {"success": False, "message": str(e)}
        else:
            return {"success": False, "message": "No availability data found in response"}
            
    except Exception as e:
        logger.error(f"Error syncing inventory for {sku}: {e}")
        return {"success": False, "message": str(e)}

def sync_all_inventory(api) -> Dict[str, Any]:
    """
    Sync inventory for all products from Walmart CA
    
    Args:
        api: WalmartCA API client
        
    Returns:
        Summary of sync operation
    """
    from products.models import Product
    
    results = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": []
    }
    
    # Get all Walmart CA products
    products = Product.objects.filter(sku__startswith="CA-")
    results["total"] = products.count()
    
    logger.info(f"Syncing inventory for {results['total']} products")
    
    for product in products:
        try:
            result = sync_inventory(api, product.sku)
            
            if result.get("success"):
                results["success"] += 1
                results["details"].append({
                    "sku": product.sku,
                    "status": "success",
                    "quantity": result.get("current_quantity")
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "sku": product.sku,
                    "status": "failed",
                    "error": result.get("message")
                })
                
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "sku": product.sku,
                "status": "error",
                "error": str(e)
            })
    
    return results