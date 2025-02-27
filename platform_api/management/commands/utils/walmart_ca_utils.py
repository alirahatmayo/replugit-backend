from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def map_to_schema(item_data: dict) -> dict:
    """
    Maps raw Walmart CA item data to our normalized schema.
    Required fields for processing: 'sku', 'name', 'platform'.

    This mapping includes:
      - sku: from item_data["sku"]
      - name: from item_data["productName"]
      - platform: hard-coded to 'walmart_ca'
      - plus additional parameters from the old mapping.
    """
    return {
        "sku": item_data.get("sku"),
        "name": item_data.get("productName"),
        "wpid": item_data.get("wpid"),
        "mart": item_data.get("mart"),
        "platform": "walmart_ca",
        "gtin": item_data.get("gtin"),
        # "wpid": item_data.get("wpid"),
        "upc": item_data.get("upc"),
        "price": item_data.get("price", {}).get("amount"),
        "currency": item_data.get("price", {}).get("currency"),
        "published_status": item_data.get("publishedStatus"),
        "lifecycle_status": item_data.get("lifecycleStatus"),
        "shelf": item_data.get("shelf"),
        "product_type": item_data.get("productType"),
        "last_updated": datetime.now().isoformat(),
    }

def extract_price_data(line):
    """
    Extracts price details including tax, discounts, and total cost for a given order line.

    Args:
        line (dict): The order line data containing pricing information.

    Returns:
        tuple: (price_data, total_price)
            - price_data (list): A list of price components including taxes and discounts.
            - total_price (float): The total price including tax.
    """
    try:
        charge_details = line.get("charges", {}).get("charge", [])
        price_data = []
        total_price = 0.0

        for charge in charge_details:
            charge_amount = charge["chargeAmount"]["amount"]
            tax_amount = charge["tax"]["taxAmount"]["amount"]
            
            total_price += charge_amount + tax_amount  # ✅ Add total price

            price_data.append({
                "chargeType": charge.get("chargeType", "UNKNOWN"),
                "chargeName": charge.get("chargeName", "UNKNOWN"),
                "amount": charge_amount,
                "currency": charge["chargeAmount"].get("currency", "USD"),
                "tax": {
                    "taxName": charge["tax"].get("taxName", "UNKNOWN"),
                    "taxAmount": tax_amount,
                },
                "isDiscount": charge.get("isDiscount", False),
            })

        return price_data, total_price  # ✅ Return extracted price details

    except Exception as e:
        logger.error(f"⚠️ Error extracting price data: {e}")
        import traceback
        traceback.print_exc()
        return [], 0.0  # ✅ Return safe defaults on error