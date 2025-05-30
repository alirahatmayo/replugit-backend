from typing import Dict, List, Any

def update_price(api, items: List[Dict]) -> Dict[str, Any]:
    """
    Update prices for multiple products
    
    Args:
        api: API client instance
        items: List of dicts with price data:
            - sku: Product SKU
            - price: Regular price
            - currency: Currency code (default: CAD)
            - sale_price: Optional sale price
            
    Returns:
        API response
    """
    price_data = {
        "PriceHeader": {
            "version": "1.1"
        },
        "Price": []
    }
    
    for item in items:
        price_item = {
            "sku": item["sku"],
            "price_data": [
                {
                    "currentPriceType": "BASE",
                    "currentPrice": {
                        "currency": item.get("currency", "CAD"),
                        "amount": str(item["price"])
                    }
                }
            ]
        }
        
        # Add sale price if provided
        if "sale_price" in item:
            price_item["price_data"].append({
                "currentPriceType": "REDUCED",
                "currentPrice": {
                    "currency": item.get("currency", "CAD"),
                    "amount": str(item["sale_price"])
                }
            })
            
        price_data["Price"].append(price_item)
        
    # Make API request
    print(f"Updating prices for {len(items)} items")
    return api.make_request('PUT', 'price', data=price_data)