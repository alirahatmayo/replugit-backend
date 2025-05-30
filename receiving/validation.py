from rest_framework import serializers

def validate_product_fields(data):
    """
    Common validation function to validate that exactly one of product or product_family is provided.
    
    Args:
        data: Dictionary of serializer data
        
    Returns:
        The validated data
        
    Raises:
        ValidationError: If neither or both product and product_family are provided
    """
    product = data.get('product')
    product_family = data.get('product_family')
    
    if not product and not product_family:
        raise serializers.ValidationError("Either product or product_family must be provided")
        
    if product and product_family:
        raise serializers.ValidationError("Only one of product or product_family can be provided")
        
    return data


def validate_destination(destination):
    """
    Validate that a destination value is among the allowed choices.
    
    Args:
        destination: The destination value to check
        
    Returns:
        The validated destination
        
    Raises:
        ValidationError: If destination is not valid
    """
    valid_destinations = ['inventory', 'qc', 'pending']
    
    if destination not in valid_destinations:
        raise serializers.ValidationError(
            f"Invalid destination: {destination}. Must be one of {valid_destinations}"
        )
        
    return destination


def validate_batch_status_for_modification(batch):
    """
    Validate that a batch can be modified based on its status.
    
    Args:
        batch: The ReceiptBatch instance
        
    Returns:
        True if the batch can be modified
        
    Raises:
        ValidationError: If batch cannot be modified
    """
    if batch.status == 'completed':
        raise serializers.ValidationError(
            f"Cannot modify batch with status 'completed'"
        )
        
    if batch.status == 'cancelled':
        raise serializers.ValidationError(
            f"Cannot modify batch with status 'cancelled'"
        )
        
    return True
