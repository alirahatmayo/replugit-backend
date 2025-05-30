"""
Common error handling utilities for the receiving app.
This module provides standardized error handling and reporting functions.
"""
import logging

logger = logging.getLogger(__name__)

class ReceivingError(Exception):
    """Base exception for receiving module errors"""
    pass

class ProcessingError(ReceivingError):
    """Error during batch or item processing"""
    pass

class ValidationError(ReceivingError):
    """Error during validation"""
    pass

class NotFoundError(ReceivingError):
    """Resource not found error"""
    pass

def handle_batch_processing_error(batch, error, log_message=None):
    """
    Standard error handling for batch processing errors.
    
    Args:
        batch: The ReceiptBatch instance that was being processed
        error: The exception that was raised
        log_message: Optional custom log message
        
    Returns:
        dict: Error context dictionary with batch info and error details
    """
    message = log_message or f"Error processing batch {batch.id}: {str(error)}"
    logger.exception(message)
    
    error_context = {
        "error": str(error),
        "batch_id": str(batch.id),
        "batch_code": batch.batch_code,
        "status": batch.status
    }
    
    return error_context

def handle_item_processing_error(item, error, log_message=None):
    """
    Standard error handling for batch item processing errors.
    
    Args:
        item: The BatchItem instance that was being processed
        error: The exception that was raised
        log_message: Optional custom log message
        
    Returns:
        dict: Error context dictionary with item info and error details
    """
    message = log_message or f"Error processing batch item {item.id}: {str(error)}"
    logger.exception(message)
    
    error_context = {
        "error": str(error),
        "item_id": str(item.id),
        "batch_id": str(item.batch.id) if item.batch else None,
        "batch_code": item.batch.batch_code if item.batch else None,
        "product": str(item.product_id) if item.product else None,
        "product_family": str(item.product_family_id) if item.product_family else None
    }
    
    return error_context
