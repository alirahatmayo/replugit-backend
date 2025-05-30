from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def ship_order_line(
    api, 
    purchase_order_id: str, 
    line_number: str,
    tracking_number: str,
    carrier_name: str = "OTHER",
    ship_date_time: str = None,
    method_code: str = "Standard",
    tracking_url: str = "",
    quantity: str = "1"
) -> Dict[str, Any]:
    """
    Mark an order line as shipped with tracking information
    
    Args:
        api: WalmartCAAPI instance
        purchase_order_id: Order ID to update
        line_number: Line number to ship
        tracking_number: Shipping tracking number
        carrier_name: Name of carrier (default: OTHER)
        ship_date_time: ISO format date (default: current time)
        method_code: Shipping method (default: Standard)
        tracking_url: URL for tracking
        quantity: Quantity shipped (default: 1)
        
    Returns:
        API response
    """
    from datetime import datetime
    
    # Use current time if not provided
    if not ship_date_time:
        ship_date_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    # Format shipping payload
    shipping_data = {
        "orderShipment": {
            "orderLines": {
                "orderLine": [
                    {
                        "lineNumber": line_number,
                        "orderLineStatuses": {
                            "orderLineStatus": [
                                {
                                    "status": "Shipped",
                                    "statusQuantity": {
                                        "unitOfMeasurement": "EACH",
                                        "amount": quantity
                                    },
                                    "trackingInfo": {
                                        "shipDateTime": ship_date_time,
                                        "carrierName": {
                                            "otherCarrier": carrier_name,
                                            "carrier": None
                                        },
                                        "methodCode": method_code,
                                        "trackingNumber": tracking_number,
                                        "trackingURL": tracking_url
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }
    
    logger.debug(f"Sending shipping update for order {purchase_order_id}, line {line_number}")
    
    # Send shipping update
    return api.make_request(
        "POST", 
        f"orders/{purchase_order_id}/shipping", 
        data=shipping_data
    )

def ship_order(api, purchase_order_id: str, shipping_info: List[Dict]) -> Dict[str, Any]:
    """
    Mark multiple order lines as shipped
    
    Args:
        api: WalmartCAAPI instance
        purchase_order_id: Order ID to update
        shipping_info: List of dicts with shipping details for each line
        
    Returns:
        Final API response
    """
    responses = []
    
    for line_info in shipping_info:
        line_response = ship_order_line(
            api,
            purchase_order_id, 
            line_number=line_info['line_number'],
            tracking_number=line_info['tracking_number'],
            carrier_name=line_info.get('carrier_name', 'OTHER'),
            ship_date_time=line_info.get('ship_date_time'),
            method_code=line_info.get('method_code', 'Standard'),
            tracking_url=line_info.get('tracking_url', ''),
            quantity=line_info.get('quantity', '1')
        )
        responses.append(line_response)
    
    return {
        "order_id": purchase_order_id,
        "lines_shipped": len(responses),
        "responses": responses
    }