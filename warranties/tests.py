# from django.forms import ValidationError
# from django.test import TestCase
# from django.utils.timezone import now
# from datetime import timedelta
# from .models import Warranty
# from .views import ActivateWarrantyView
# from products.models import ProductUnit
# from customers.models import Customer

# class WarrantyTests(TestCase):
#     def setUp(self):
#         self.customer = Customer.objects.create(
#             name="Test Customer",
#             email="test@example.com",
#             phone_number="1234567890"
#         )
#         self.product_unit = ProductUnit.objects.create(
#             serial_number="TEST123"
#         )
#         self.warranty = Warranty.objects.create(
#             product_unit=self.product_unit,
#             purchase_date=now().date(),
#             warranty_period=3
#         )

#     def test_warranty_activation(self):
#         self.warranty.transition_status('active')
#         self.assertEqual(self.warranty.status, 'active')
#         self.assertIsNotNone(self.warranty.registered_at)

#     def test_warranty_extension(self):
#         self.warranty.transition_status('active')
#         original_expiration = self.warranty.warranty_expiration_date
#         self.warranty.extend_warranty(3)
#         self.assertTrue(self.warranty.is_extended)
#         self.assertEqual(
#             self.warranty.warranty_expiration_date,
#             original_expiration + timedelta(days=90)
#         )

#     def test_invalid_status_transition(self):
#         with self.assertRaises(ValidationError):
#             self.warranty.transition_status('expired')
