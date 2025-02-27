from orders.models import Customer, Product, ProductUnit, Order, OrderItem, Warranty
from rest_framework.test import APITestCase
from django.utils.timezone import now

class SignalTests(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="John Doe", email="john@example.com", phone_number="1234567890")
        self.product = Product.objects.create(product_name="Test Product")
        self.product_unit = ProductUnit.objects.create(serial_number="SN12345", product=self.product)
        self.order = Order.objects.create(customer=self.customer, order_number="ORD001")
        self.order_item = OrderItem.objects.create(order=self.order, product=self.product, product_unit=self.product_unit)

    def test_create_warranty_on_shipment(self):
        # Set shipping_date to pass validation
        self.order.state = 'shipped'
        self.order.shipping_date = now().date()  # Set a valid shipping date
        self.order.save()

        # Check if warranty is created
        warranty = Warranty.objects.filter(product_unit=self.product_unit).first()
        self.assertIsNotNone(warranty)
        self.assertEqual(warranty.status, 'not_registered')
