"""
Utility functions for the receiving module.
Contains common destination logic, validation utilities, and other shared functionality.
"""

def get_destination_display(destination_code):
    """
    Get human-readable display text for a destination code.
    
    Args:
        destination_code: String code ('inventory', 'qc', or 'pending')
        
    Returns:
        String: Human-readable display text
    """
    destination_map = {
        'inventory': 'Direct to Inventory',
        'qc': 'Quality Control',
        'pending': 'Pending Decision'
    }
    
    return destination_map.get(destination_code, destination_code)


def should_require_qc(item):
    """
    Determine if an item should require QC based on business rules.
    
    Args:
        item: BatchItem instance
        
    Returns:
        bool: True if QC should be required
    """
    # Current business rules:
    # - Items with certain condition codes always require QC
    # - Items from certain suppliers might require QC
    
    # Future rule examples (placeholders):
    # if item.condition_grade and item.condition_grade != 'A':
    #     return True
    # 
    # if item.batch.seller_info and item.batch.seller_info.get('require_qc'):
    #     return True
    
    # For now, return the existing flag
    return item.requires_unit_qc
    

def get_default_destination(item):
    """
    Determine the default destination for an item based on business rules.
    
    Args:
        item: BatchItem instance
        
    Returns:
        str: Destination code ('inventory', 'qc', or 'pending')
    """
    if should_require_qc(item):
        return 'qc'
    else:
        return 'inventory'
