# products/services/validation.py

from products.models import ProductUnit

def validate_product_unit(serial_number, activation_code):
    """
    Validate a ProductUnit by its serial number and activation code.

    Returns a tuple: (is_valid, product_unit or error_message)
    
    - If valid, returns (True, product_unit instance).
    - If invalid, returns (False, <error message string>).
    """
    if not serial_number or not activation_code:
        return (False, "Both serial number and activation code must be provided.")

    try:
        # Look up the product unit using a case-insensitive match on activation code.
        product_unit = ProductUnit.objects.get(
            serial_number=serial_number,
            activation_code__iexact=activation_code
        )
    except ProductUnit.DoesNotExist:
        return (False, "No product unit found with the provided serial number and activation code.")

    # Optionally, add additional checks.
    # For example, you might check if the product unit is already assigned or not in stock.
    if product_unit.status != 'in_stock':
        return (False, "This product unit is not available for activation.")

    # If all checks pass, return valid.
    return (True, product_unit)
