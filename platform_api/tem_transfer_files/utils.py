from orders.models import Order, OrderItem


def map_walmart_state_to_internal(state):
    """
    Maps Walmart order states to internal states.
    """
    state_mapping = {
        'Created': 'created',
        'Acknowledged': 'acknowledged',
        'Shipped': 'shipped',
        'Cancelled': 'cancelled',
    }
    return state_mapping.get(state, 'unknown')


def save_order_and_items(platform, order_data):
    """
    Saves order and items for a specific platform.
    """
    order, created = Order.objects.update_or_create(
        platform_order_id=order_data['purchaseOrderId'],
        defaults={
            'order_number': order_data['customerOrderId'],
            'platform': platform,
            'state': map_walmart_state_to_internal(order_data['orderStatus']),
            'order_date': order_data['purchaseDate'],
            'platform_specific_data': order_data,
        }
    )

    for item_data in order_data['orderLines']:
        OrderItem.objects.update_or_create(
            order=order,
            product_unit_id=item_data['sku'],
            defaults={
                'status': item_data['status'],
                'customer': order.customer,
            }
        )
