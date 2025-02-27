
from rest_framework.test import APITestCase
from rest_framework import status
from orders.models import Customer, Product, ProductUnit, Order, OrderItem
from django.utils.timezone import now

class OrderViewSetTests(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="John Doe", email="john@example.com", phone_number="1234567890")
        self.product = Product.objects.create(product_name="Test Product")
        self.product_unit = ProductUnit.objects.create(serial_number="SN12345", product=self.product)
        self.order = Order.objects.create(customer=self.customer, order_number="ORD001")
        self.order_item = OrderItem.objects.create(order=self.order, product=self.product, product_unit=self.product_unit)

    def test_confirm_order(self):
        response = self.client.post(f"/api/orders/{self.order.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.state, 'confirmed')

    def test_ship_order(self):
        # Confirm the order before shipping
        self.client.post(f"/api/orders/{self.order.id}/confirm/")

        # Ship the order with a valid shipping_date
        response = self.client.post(
            f"/api/orders/{self.order.id}/ship/",
            {"shipping_date": str(now().date())}
        )
        print(response.json())  # Debugging: Check the response if it fails
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.state, 'shipped')

    def test_invalid_ship_order_without_date(self):
        response = self.client.post(f"/api/orders/{self.order.id}/ship/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_order(self):
        response = self.client.post(f"/api/orders/{self.order.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.state, 'cancelled')