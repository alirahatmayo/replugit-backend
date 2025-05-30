import json
from typing import Dict, List, Optional

def get_products(
    api,
    sku: Optional[str] = None,
    limit: int = 50,
    next_cursor: Optional[str] = None,
    offset: Optional[int] = None,
    lifecycleStatus: Optional[str] = None,
    publishedStatus: Optional[str] = None,
    variantGroupId: Optional[str] = None,
    process: bool = True,
    dry_run: bool = False  # New parameter - don't save when True
) -> List[Dict]:
    """
    Fetch products with all available filters from Walmart CA API
    
    Args:
        api: API client instance
        sku: Filter by specific SKU
        limit: Maximum number of products to return (max 50)
        next_cursor: Pagination cursor for fetching next set
        offset: Alternative pagination using offset
        lifecycleStatus: Filter by lifecycle status (ACTIVE, ARCHIVED, RETIRED)
        publishedStatus: Filter by published status (PUBLISHED, UNPUBLISHED)
        variantGroupId: Filter by variant group ID
        process: Whether to process products through the processor
        dry_run: If True, process but don't save to database
        
    Returns:
        List of processed products or raw API response
    """
    params = {'limit': limit}
    
    # Add optional parameters
    if sku:
        params['sku'] = sku
        
    if next_cursor:
        params['nextCursor'] = next_cursor
    elif offset is not None:
        params['offset'] = offset
        
    if lifecycleStatus:
        params['lifecycleStatus'] = lifecycleStatus
        
    if publishedStatus:
        params['publishedStatus'] = publishedStatus
        
    if variantGroupId:
        params['variantGroupId'] = variantGroupId
    
    # Make API request
    print(f"Fetching products with params: {params}")
    response = api.make_request('GET', 'items', params=params)
    
    print(f"API Response Structure: {type(response)}")
    if isinstance(response, dict):
        print(f"Response keys: {list(response.keys())}")
        if 'ItemResponse' in response:
            print(f"Found {len(response['ItemResponse'])} items")
            if response['ItemResponse'] and len(response['ItemResponse']) > 0:
                first_item = response['ItemResponse'][0]
                print(f"First item keys: {list(first_item.keys())}")
                print(f"Example item data: {json.dumps(first_item, indent=2)[:500]}...")
    
    # Process products if requested (and automatically save)
    if process and response:
        from .processor import WalmartCAProductProcessor
        processor = WalmartCAProductProcessor()
        
        products = []
        # Extract products correctly from nested structure
        items = []
        if isinstance(response, dict) and 'ItemResponse' in response:
            items = response.get('ItemResponse', [])
            
        for product_data in items:
            try:
                processed_product = processor.process_product(product_data)
                if processed_product:
                    products.append(processed_product)
                    
                    # Save to database by default unless dry_run is True
                    if not dry_run:
                        product, created = processor.save_product(processed_product)
                        status = "created" if created else "updated"
                        print(f"Product {processed_product['sku']} {status} in database")
                    else:
                        print(f"Dry run: Product {processed_product['sku']} would be saved")
            except Exception as e:
                import traceback
                print(f"Error processing product: {e}")
                print(traceback.format_exc())
                
        return products
        
    return response

def get_all_products(api, **kwargs):
    """Get all products with pagination using offset"""
    all_products = []
    processed_products = []
    
    # Remove process flag to avoid duplication but store it
    process_param = kwargs.pop('process', True) if 'process' in kwargs else True
    dry_run = kwargs.pop('dry_run', False) if 'dry_run' in kwargs else False
    
    # Start with offset 0 if not specified
    offset = kwargs.pop('offset', 0)
    
    # Use provided limit or default to 50
    limit = kwargs.get('limit', 50)
    if not limit:
        limit = 50
    
    print(f"Starting product pagination with limit {limit}")
    page = 1
    
    try:
        while True:
            print(f"Fetching products page {page} (offset: {offset})...")
            
            # Create request params for this page
            current_params = dict(kwargs)
            current_params['offset'] = offset
            current_params['process'] = False  # Don't process yet
            
            # Make the API call
            response = get_products(api, **current_params)
            
            # Extract items from response
            items = []
            if isinstance(response, dict) and 'ItemResponse' in response:
                items = response['ItemResponse']
                print(f"Found {len(items)} items on page {page}")
                
                # Add items to our collection
                all_products.extend(items)
                
                # Increment offset for next page
                offset += len(items)
                
                # If fewer items than requested, we've reached the end
                if len(items) < limit:
                    print("Reached last page (fewer items than limit)")
                    break
            else:
                print("No ItemResponse found in response or empty items")
                break
            
            page += 1
            
    except Exception as e:
        import traceback
        print(f"Error during pagination: {e}")
        print(traceback.format_exc())
    
    print(f"Total products collected: {len(all_products)}")
    
    # Now process all products if requested
    if process_param and all_products:
        from .processor import WalmartCAProductProcessor
        processor = WalmartCAProductProcessor()
        
        for item in all_products:
            try:
                processed_product = processor.process_product(item)
                if processed_product:
                    processed_products.append(processed_product)
                    if not dry_run:
                        product, created = processor.save_product(processed_product)
                        status = "created" if created else "updated"
                        print(f"Product {processed_product.get('sku')} {status}")
            except Exception as e:
                print(f"Error processing product: {e}")
                
        return processed_products
    
    return all_products