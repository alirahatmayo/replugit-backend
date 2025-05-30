from typing import Dict, List, Optional, Any
import logging
import json

logger = logging.getLogger(__name__)

def update_inventory(
    api,
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update inventory on Walmart CA
    
    API: PUT https://marketplace.walmartapis.com/v3/ca/inventory
    
    Args:
        api: WalmartCA API client
        items: List of dictionaries with inventory data
              Format: [{'sku': 'SKU1', 'quantity': 10, 'lag_time': 1}, ...]
    
    Returns:
        API response
    """
    if not items:
        logger.warning("No items provided for inventory update")
        return {"success": False, "message": "No items provided"}
    
    results = {
        "success": 0,
        "failed": 0,
        "items": []
    }
    
    # Process each item individually
    for item in items:
        if not item.get("sku"):
            logger.error("Item missing SKU, skipping")
            results["failed"] += 1
            continue
            
        # Remove CA- prefix if present
        sku = item["sku"]
        if sku.startswith("CA-"):
            sku = sku[3:]
            
        # Get quantity with validation
        qty = item.get("quantity", 0)
        if qty < 0:
            logger.warning(f"Negative quantity {qty} for SKU {sku}, setting to 0")
            qty = 0
            
        # Get lag time with default
        lag_time = item.get("lag_time", 1)
        
        # Build the inventory update payload according to API spec
        inventory_data = {
            "sku": sku,
            "quantity": {
                "unit": "EACH",
                "amount": qty
            },
            "fulfillmentLagTime": lag_time
        }
        
        # Optional fields
        if "partner_id" in item:
            inventory_data["partnerId"] = item["partner_id"]
            
        if "offer_id" in item:
            inventory_data["offerId"] = item["offer_id"]
        
        # Query parameter must include SKU
        params = {"sku": sku}
        
        try:
            logger.info(f"Updating inventory for SKU {sku} to {qty}")
            logger.debug(f"Inventory update data: {json.dumps(inventory_data)}")
            
            # Make API request
            response = api.make_request('PUT', 'inventory', params=params, data=inventory_data)
            
            if response:
                results["success"] += 1
                results["items"].append({
                    "sku": sku,
                    "status": "success",
                    "response": response
                })
                
                # Update local inventory if successful
                try:
                    from inventory.models import Inventory, Location
                    from products.models import Product
                    
                    # Get product and location
                    product_sku = f"CA-{sku}" if not sku.startswith("CA-") else sku
                    product = Product.objects.get(sku=product_sku)
                    
                    location, _ = Location.objects.get_or_create(
                        code='WALMART_CA',
                        defaults={'name': 'Walmart CA'}
                    )
                    
                    # Update inventory
                    inventory, created = Inventory.objects.get_or_create(
                        product=product,
                        platform='walmart_ca',
                        location=location,
                        defaults={'quantity': 0}
                    )
                    
                    # Record history
                    prev_qty = inventory.quantity
                    inventory.quantity = qty
                    inventory.save()
                    
                    # Create history entry
                    from inventory.models import InventoryHistory
                    InventoryHistory.objects.create(
                        inventory=inventory,
                        previous_quantity=prev_qty,
                        new_quantity=qty,
                        change=qty - prev_qty,
                        reason='SYNC',
                        reference=f"API Update {response.get('feedId', '')}"
                    )
                    
                except Product.DoesNotExist:
                    logger.warning(f"Product not found for SKU: {product_sku}")
                except Exception as e:
                    logger.error(f"Error updating local inventory: {e}")
                    
            else:
                results["failed"] += 1
                results["items"].append({
                    "sku": sku,
                    "status": "failed",
                    "error": "No response from API"
                })
                
        except Exception as e:
            results["failed"] += 1
            results["items"].append({
                "sku": sku,
                "status": "error",
                "error": str(e)
            })
            logger.error(f"Error updating inventory for {sku}: {e}")
    
    # Return consolidated results
    return {
        "total": len(items),
        "success": results["success"],
        "failed": results["failed"],
        "items": results["items"]
    }