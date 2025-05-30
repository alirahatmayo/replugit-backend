from datetime import datetime
from typing import Dict, List, Optional
from .processor import WalmartCAOrderProcessor  # Local import from orders directory

def get_orders(
    api,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = 100,
    status: str = None,
    next_cursor: str = None,
    acknowledgeable: bool = None,
    customer_order_id: str = None,
    purchase_order_id: str = None,
    order_date_start: str = None,
    order_date_end: str = None,
    # New parameters
    sku: str = None,
    from_expected_ship_date: str = None,
    to_expected_ship_date: str = None,
    product_info: bool = False,
    process: bool = True
) -> List[Dict]:
    """
    Fetch orders with all available filters from Walmart CA API
    
    Args:
        api: API client instance
        start_date: Start date for created date filter (YYYY-MM-DD)
        end_date: End date for created date filter (YYYY-MM-DD)
        created_after: Alternative to start_date
        created_before: Alternative to end_date
        limit: Maximum number of orders to return (max 200)
        status: Filter by order status (Created, Acknowledged, Shipped, Cancelled)
        next_cursor: Pagination cursor for fetching next set of orders
        acknowledgeable: Filter by acknowledgeable status
        customer_order_id: Filter by customer order ID
        purchase_order_id: Filter by purchase order ID
        order_date_start: Filter by order date (start)
        order_date_end: Filter by order date (end)
        sku: Filter by specific product SKU
        from_expected_ship_date: Filter by expected ship date (from)
        to_expected_ship_date: Filter by expected ship date (to)
        product_info: Include product information in response
        process: Whether to process orders through the processor
        
    Returns:
        List of processed orders or raw API response
    """
    params = {'limit': limit}
    
    # Support both new and old parameter names
    actual_start_date = start_date or created_after
    actual_end_date = end_date or created_before
    
    # Date parameter formatting
    if actual_start_date:
        if isinstance(actual_start_date, str):
            params['createdStartDate'] = f"{actual_start_date}T00:00:00.000Z"
        else:
            params['createdStartDate'] = actual_start_date.strftime('%Y-%m-%dT00:00:00.000Z')
    
    if actual_end_date:
        if isinstance(actual_end_date, str):
            params['createdEndDate'] = f"{actual_end_date}T23:59:59.999Z"
        else:
            params['createdEndDate'] = actual_end_date.strftime('%Y-%m-%dT23:59:59.999Z')
    
    # Add other optional parameters
    if status and status != 'all':
        params['status'] = status
    
    if next_cursor:
        params['nextCursor'] = next_cursor
        
    if customer_order_id:
        params['customerOrderId'] = customer_order_id
        
    if purchase_order_id:
        params['purchaseOrderId'] = purchase_order_id
    
    # Add new parameters from API documentation
    if sku:
        params['sku'] = sku
        
    # Ship date parameters
    if from_expected_ship_date:
        params['fromExpectedShipDate'] = from_expected_ship_date
        
    if to_expected_ship_date:
        params['toExpectedShipDate'] = to_expected_ship_date
        
    # Product info parameter (boolean flag)
    if product_info:
        params['productInfo'] = 'true'
        
    # Make API request
    print(f"Fetching orders with params: {params}")
    response = api.make_request('GET', 'orders', params=params)
    
    # Process orders
    if process and response:
        processor = WalmartCAOrderProcessor()
        processed_orders = []
        
        # Extract orders correctly from nested structure
        orders = []
        if isinstance(response, dict) and 'list' in response:
            element_orders = response.get('list', {}).get('elements', {}).get('order', [])
            if element_orders:
                orders = element_orders
                print(f"Successfully extracted {len(orders)} orders from nested response")
            else:
                print(f"Warning: Could not find orders at the expected path. Response keys: {response.keys()}")
        
        for order_data in orders:
            try:
                print(f"Processing order: {order_data.get('purchaseOrderId', 'Unknown')}")
                # Pass debug=True to print more info during processing
                processed_order = processor.process_order(order_data)
                if processed_order:
                    processed_orders.append(processed_order)
            except Exception as e:
                import traceback
                print(f"Error processing order: {e}")
                print(traceback.format_exc())
                continue
                
        return processed_orders
    
    return response

def get_order(api, purchase_order_id: str, process: bool = True) -> Optional[Dict]:
    """Fetch a single order by ID"""
    response = api.make_request('GET', f'orders/{purchase_order_id}')
    
    if process and response:
        processor = WalmartCAOrderProcessor()
        return processor.process_order(response)
    return response

def get_all_orders(api, **kwargs) -> List[Dict]:
    """
    Fetch all orders using pagination
    
    This function will automatically handle pagination by following the nextCursor
    until all matching orders have been retrieved.
    
    Args:
        api: API client instance
        **kwargs: All parameters accepted by get_orders()
        
    Returns:
        List of all orders across all pages
    """
    all_orders = []
    next_cursor = None
    page = 1
    
    # Force processing to be enabled
    kwargs['process'] = True
    
    while True:
        print(f"Fetching orders page {page}...")
        
        # Add cursor to params if we have one
        if next_cursor:
            kwargs['next_cursor'] = next_cursor
            
        # Get this page of orders
        page_orders = get_orders(api, **kwargs)
        
        if not page_orders:
            print(f"No orders returned on page {page}")
            break
            
        # Add to our collected orders
        all_orders.extend(page_orders)
        print(f"Added {len(page_orders)} orders from page {page}, total: {len(all_orders)}")
        
        # Get raw response to check for more pages
        raw_response = get_orders(api, next_cursor=next_cursor, process=False, **kwargs)
        
        # Extract next_cursor from response metadata
        if isinstance(raw_response, dict) and 'list' in raw_response:
            meta = raw_response.get('list', {}).get('meta', {})
            next_cursor = meta.get('nextCursor')
            
            if next_cursor:
                print(f"Found next_cursor: {next_cursor[:30]}...")
            else:
                print("No more pages")
                break
        else:
            # If we can't get metadata, stop paging
            break
            
        page += 1
        
    print(f"Total orders fetched: {len(all_orders)}")
    return all_orders