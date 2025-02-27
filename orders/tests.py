# from django.test import TestCase
# from django.core.exceptions import ValidationError
# from orders.models import Customer, Product, Order, ProductUnit, OrderItem
# from warranties.models import Warranty

# class OrderModelTest(TestCase):
#     def setUp(self):
#         self.customer = Customer.objects.create(name="John Doe")
#         self.product = Product.objects.create(product_name="Laptop", category="Electronics", stock=10)
#         self.product_unit = ProductUnit.objects.create(product=self.product, serial_number="12345")
#         self.order = Order.objects.create(customer=self.customer, state='created')

#     def test_order_state_transition(self):
#         self.order.transition_state('confirmed')
#         self.assertEqual(self.order.state, 'confirmed')

#     def test_invalid_order_state_transition(self):
#         with self.assertRaises(ValidationError):
#             self.order.transition_state('shipped')

#     def test_order_item_validation(self):
#         item = OrderItem.objects.create(
#             order=self.order,
#             product=self.product,
#             product_unit=self.product_unit,
#             quantity=2
#         )
#         self.assertEqual(item.quantity, 2)

#     def test_order_item_product_unit_mismatch(self):
#         another_product = Product.objects.create(product_name="Phone", category="Electronics")
#         with self.assertRaises(ValidationError):
#             OrderItem.objects.create(
#                 order=self.order,
#                 product=another_product,
#                 product_unit=self.product_unit,
#                 quantity=1
#             )

#     def test_stock_adjustment_on_order_creation(self):
#         OrderItem.objects.create(
#             order=self.order,
#             product=self.product,
#             product_unit=self.product_unit,
#             quantity=2
#         )
#         self.product.refresh_from_db()
#         self.assertEqual(self.product.stock, 8)

#     def test_warranty_creation_on_shipment(self):
#         self.order.transition_state('shipped')
#         self.order.product_unit = self.product_unit
#         self.order.save()
#         warranty = Warranty.objects.filter(product_unit=self.product_unit).first()
#         self.assertIsNotNone(warranty)
#         self.assertEqual(warranty.status, 'not_registered')

#     def test_order_creation_with_items(self):
#         item = OrderItem.objects.create(
#             order=self.order,
#             product=self.product,
#             product_unit=self.product_unit,
#             quantity=2
#         )
#         self.assertEqual(self.order.items.count(), 1)
#         self.assertEqual(item.quantity, 2)
