from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

def acknowledge_order(api, purchase_order_id: str, line_numbers=None) -> Dict[str, Any]:
    """
    Acknowledge an order to confirm receipt
    
    Args:
        api: WalmartCAAPI instance
        purchase_order_id: The purchase order ID to acknowledge
        line_numbers: Optional specific line numbers to acknowledge. If None, acknowledges entire order.
        
    Returns:
        API response
    """
    # If no line numbers provided, acknowledge the entire order
    if line_numbers is None or len(line_numbers) == 0:
        logger.info(f"Acknowledging entire order {purchase_order_id}")
        
        # For entire order acknowledgment, we can use an empty payload or {}
        # The documentation suggests this is sufficient for the /acknowledge endpoint
        return api.make_request(
            "POST", 
            f"orders/{purchase_order_id}/acknowledge",
            data={}  # Empty payload for full order acknowledgment
        )
    else:
        # For specific lines, use the acknowledgeLines endpoint with proper payload
        logger.info(f"Acknowledging specific lines {line_numbers} for order {purchase_order_id}")
        
        # Format according to acknowledgeLines documentation
        order_line_statuses = []
        for line_num in line_numbers:
            order_line_statuses.append({
                "lineNumber": line_num,
                "orderLineStatuses": {
                    "orderLineStatus": [
                        {
                            "status": "CREATED",
                            "statusQuantity": {
                                "unitOfMeasurement": "EACH",
                                "amount": "1"  # Assuming full line quantity
                            }
                        }
                    ]
                }
            })
        
        acknowledgement_data = {
            "orderLines": {
                "orderLine": order_line_statuses
            }
        }
        
        # Send acknowledgement for specific lines
        return api.make_request(
            "POST", 
            f"orders/{purchase_order_id}/acknowledgeLines",
            data=acknowledgement_data
        )