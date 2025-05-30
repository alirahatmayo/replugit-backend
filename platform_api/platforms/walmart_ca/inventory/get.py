from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

def get_inventory(
    api,
    sku: str
) -> Dict[str, Any]:
    """
    Get inventory for a specific product using the dedicated inventory API
    
    API: https://marketplace.walmartapis.com/v3/ca/inventory
    
    Args:
        api: WalmartCA API client
        sku: Product SKU
        
    Returns:
        Inventory information
    """
    if not sku:
        return {"success": False, "message": "No SKU provided"}
        
    # Remove CA- prefix if needed
    if sku.startswith("CA-"):
        api_sku = sku[3:]
    else:
        api_sku = sku
        
    try:
        # Call the inventory API endpoint with sku as query param
        params = {'sku': api_sku}
        logger.info(f"Fetching inventory for SKU {api_sku} from inventory API")
        
        response = api.make_request('GET', 'inventory', params=params)
        
        if not response:
            return {"success": False, "message": "No response from API"}
            
        logger.debug(f"Inventory response: {response}")
        return {
            "success": True,
            "sku": sku,
            "inventory_data": response
        }
            
    except Exception as e:
        logger.error(f"Error getting inventory for {sku}: {e}")
        return {"success": False, "message": str(e)}

def get_inventory_status(
    api,
    sku: str
) -> Dict[str, Any]:
    """Get inventory status for a product on Walmart CA"""
    # Use the direct inventory API endpoint
    inventory_response = get_inventory(api, sku)
    
    if not inventory_response.get('success'):
        return inventory_response
    
    # Extract inventory status from the API response
    inventory_data = inventory_response.get('inventory_data', {})
    
    try:
        status_data = {
            "success": True,
            "sku": sku,
            "status": "OUT_OF_STOCK",  # Default status
            "quantity": 0              # Default quantity
        }
        
        # Handle nested quantity structure
        if 'quantity' in inventory_data and isinstance(inventory_data['quantity'], dict):
            # Extract amount from quantity object
            status_data['quantity'] = int(inventory_data['quantity'].get('amount', 0))
            status_data['unit'] = inventory_data['quantity'].get('unit', 'EACH')
        
        # Handle fulfillment lag time
        if 'fulfillmentLagTime' in inventory_data:
            status_data['lag_time'] = inventory_data['fulfillmentLagTime']
            
        # Set status based on quantity
        status_data['status'] = 'IN_STOCK' if status_data['quantity'] > 0 else 'OUT_OF_STOCK'
            
        # Get local inventory for comparison
        try:
            from inventory.models import Inventory
            from products.models import Product
            
            product_sku = sku if sku.startswith("CA-") else f"CA-{sku}"
            local_inventory = Inventory.objects.filter(
                product__sku=product_sku,
                platform='walmart_ca'
            ).first()
            
            if local_inventory:
                status_data["local_quantity"] = local_inventory.quantity
                status_data["local_status"] = local_inventory.status
                status_data["synced"] = (local_inventory.quantity == status_data["quantity"])
            else:
                status_data["local_quantity"] = None
                status_data["local_status"] = None
                status_data["synced"] = False
            
        except Exception as e:
            logger.error(f"Error getting local inventory: {e}")
            status_data["error"] = str(e)
            
        return status_data
            
    except Exception as e:
        logger.error(f"Error parsing inventory data: {e}")
        return {
            "success": False, 
            "message": f"Error parsing inventory data: {e}",
            "raw_data": inventory_data
        }

def get_low_stock_items(
    api,
    threshold: int = 5
) -> List[Dict[str, Any]]:
    """
    Get all items with low stock on Walmart CA
    
    Args:
        api: WalmartCA API client
        threshold: Quantity threshold to consider "low stock"
        
    Returns:
        List of items with low stock
    """
    # Use local database query for efficiency
    try:
        from inventory.models import Inventory
        
        # Find low stock items in local inventory
        low_stock = Inventory.objects.filter(
            platform='walmart_ca',
            quantity__gt=0,
            quantity__lte=threshold
        ).select_related('product')
        
        results = []
        
        for item in low_stock:
            results.append({
                "sku": item.product.sku,
                "name": item.product.name,
                "quantity": item.quantity,
                "status": item.status,
                "location": item.location.name,
                "last_updated": item.updated_at
            })
            
        return results
        
    except Exception as e:
        logger.error(f"Error getting low stock items: {e}")
        return []