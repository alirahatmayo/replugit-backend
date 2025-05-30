from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LocationViewSet, InventoryViewSet, InventoryHistoryViewSet,
    InventoryReceiptViewSet, InventoryAdjustmentViewSet,
    inventory_dashboard, allocate_units, test_receipt_units
)

router = DefaultRouter()
router.register(r'locations', LocationViewSet)
router.register(r'inventory', InventoryViewSet)
router.register(r'history', InventoryHistoryViewSet)
router.register(r'receipts', InventoryReceiptViewSet)
router.register(r'adjustments', InventoryAdjustmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', inventory_dashboard, name='inventory_dashboard'),
    path('allocate/', allocate_units, name='allocate_units'),
    path('test-receipt/<uuid:receipt_id>/units/', test_receipt_units, name='test_receipt_units'),
]

# customers/urls.py

# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views import CustomerViewSet

# router = DefaultRouter()
# router.register(r'', CustomerViewSet)

# urlpatterns = [
#     path('', include(router.urls)),
# ]
