import json
from typing import Dict, List

def get_order_line_numbers(order_data: Dict) -> List[str]:
    """Extract line numbers from order data for shipping/cancellation operations"""
    lines = []
    
    # Debug the structure
    print(f"Order data structure (partial):", json.dumps(list(order_data.keys())[:10], indent=2))
    
    # Handle both single order and list of orders
    if 'orderLines' in order_data:
        # Direct order object
        order_lines = order_data.get('orderLines', {}).get('orderLine', [])
    elif 'order' in order_data:
        # Order wrapped in another object
        order_lines = order_data.get('order', {}).get('orderLines', {}).get('orderLine', [])
    else:
        print(f"Unexpected order data structure. Keys: {list(order_data.keys())}")
        order_lines = []
    
    # Extract line numbers
    for line in order_lines:
        line_number = line.get('lineNumber')
        if line_number:
            lines.append(line_number)
            
    print(f"Found {len(lines)} line items: {lines}")
    return lines