from typing import Dict, List, Any

def update_inventory(api, items: List[Dict]) -> Dict[str, Any]:
    """
    Update inventory for multiple products
    
    Args:
        api: API client instance
        items: List of dicts with inventory data:
            - sku: Product SKU
            - quantity: Available quantity
            - fulfillment_center: Optional fulfillment center ID
            
    Returns:
        API response
    """
    inventory_data = {
        "inventory": {
            "sku": [],
            "quantity": []
        }
    }
    
    for item in items:
        inventory_data["inventory"]["sku"].append(item["sku"])
        inventory_data["inventory"]["quantity"].append(str(item["quantity"]))
        
    # Make API request
    print(f"Updating inventory for {len(items)} items")
    return api.make_request('PUT', 'inventory', data=inventory_data)