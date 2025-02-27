from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.forms import ValidationError
from orders.models import Order, OrderItem
from products.models import Product, ProductUnit
from customers.models import Customer
from warranties.models import Warranty
from django.utils.timezone import now
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

class OrderModelTests(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="John Doe",
            email="john@example.com",
            phone_number="1234567890"
        )
        self.product = Product.objects.create(product_name="Test Product")
        self.product_unit = ProductUnit.objects.create(
            serial_number="SN12345",
            product=self.product
        )
        self.order = Order.objects.create(
            customer=self.customer,
            order_number="ORD001"
        )

    def test_order_creation(self):
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.order.customer, self.customer)
        self.assertEqual(self.order.state, 'created')

    def test_invalid_state_transition(self):
        self.order.state = 'shipped'
        self.order.shipping_date = now()
        self.order.save()


class OrderItemModelTests(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="John Doe", email="john@example.com", phone_number="1234567890")
        self.product = Product.objects.create(product_name="Test Product")
        self.product_unit = ProductUnit.objects.create(serial_number="SN12345", product=self.product)
        self.order = Order.objects.create(customer=self.customer, order_number="ORD001")
        self.order_item = OrderItem.objects.create(order=self.order, product=self.product, product_unit=self.product_unit)

    def test_order_item_creation(self):
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(self.order_item.order, self.order)
        self.assertEqual(self.order_item.product_unit, self.product_unit)

    def test_order_item_validation(self):
        # Create invalid order item without required fields
        invalid_item = OrderItem(
            order=self.order,
            # Missing product_unit and other required fields
        )
        with self.assertRaises(ValidationError):
            invalid_item.full_clean()  # Use full_clean() instead of save()

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
        # Confirm the order first
        self.client.post(f"/api/orders/{self.order.id}/confirm/")

        # Then ship the order
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



class SignalTests(APITestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="John Doe", 
            email="john@example.com", 
            phone_number="1234567890"
        )
        self.product = Product.objects.create(
            product_name="Test Product"
        )
        self.product_unit = ProductUnit.objects.create(
            serial_number="SN12345",
            product=self.product
        )
        self.order = Order.objects.create(
            customer=self.customer,
            order_number="ORD001"
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_unit=self.product_unit
        )

    def test_create_warranty_on_shipment(self):
        self.order.state = 'shipped'
        self.order.shipping_date = now().date()  # Set the required shipping_date
        self.order.save()
        warranty = Warranty.objects.filter(product_unit=self.product_unit).first()
        self.assertIsNotNone(warranty)
        self.assertEqual(warranty.status, 'not_registered')
