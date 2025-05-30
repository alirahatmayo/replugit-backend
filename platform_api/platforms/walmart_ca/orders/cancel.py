import json
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Valid cancellation reasons according to API documentation
VALID_CANCELLATION_REASONS = [
    "CANCEL_BY_SELLER", 
    "CUSTOMER_REQUESTED_SELLER_TO_CANCEL"
]

def cancel_order_line(
    api, 
    purchase_order_id: str,  # Correct format - variable: type
    line_number: str,        # Correct format
    cancellation_reason: str = "CANCEL_BY_SELLER",
    quantity: str = "1"
) -> Dict[str, Any]:
    """
    Cancel a specific order line
    
    Args:
        api: WalmartCAAPI instance
        purchase_order_id: Order ID
        line_number: Line number to cancel
        cancellation_reason: Reason for cancellation (use VALID_CANCELLATION_REASONS)
        quantity: Quantity to cancel (default: all)
        
    Returns:
        API response
    """
    # Validate cancellation reason
    if cancellation_reason not in VALID_CANCELLATION_REASONS:
        logger.warning(f"Invalid cancellation reason: {cancellation_reason}. Using CANCEL_BY_SELLER.")
        cancellation_reason = "CANCEL_BY_SELLER"
    
    # Build cancel request according to XSD schema
    cancel_data = {
        "orderCancellation": {
            "orderLines": {
                "orderLine": [
                    {
                        "lineNumber": line_number,
                        "orderLineStatuses": {
                            "orderLineStatus": [
                                {
                                    "status": "Cancelled",
                                    "cancellationReason": cancellation_reason,
                                    "statusQuantity": {
                                        "unitOfMeasurement": "EACH",
                                        "amount": quantity
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }
    
    logger.info(f"Cancelling order {purchase_order_id}, line {line_number} with reason: {cancellation_reason}")
    
    return api.make_request(
        "POST", 
        f"orders/{purchase_order_id}/cancel", 
        data=cancel_data
    )

def cancel_order(api, purchase_order_id: str, cancellations: List[Dict]) -> Dict[str, Any]:
    """
    Cancel multiple order lines
    
    Args:
        api: WalmartCAAPI instance
        purchase_order_id: Order ID
        cancellations: List of dicts with line cancellation details:
            - line_number: Line number to cancel
            - reason: Cancellation reason (CANCEL_BY_SELLER or CUSTOMER_REQUESTED_SELLER_TO_CANCEL)
            - quantity: Optional quantity to cancel
        
    Returns:
        Combined response
    """
    responses = []
    
    for cancel_info in cancellations:
        response = cancel_order_line(
            api,
            purchase_order_id,
            line_number=cancel_info['line_number'],
            cancellation_reason=cancel_info.get('reason', 'CANCEL_BY_SELLER'),
            quantity=cancel_info.get('quantity', '1')
        )
        responses.append(response)
    
    return {
        "order_id": purchase_order_id,
        "lines_cancelled": len(responses),
        "responses": responses
    }