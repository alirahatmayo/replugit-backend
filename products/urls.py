from rest_framework.routers import DefaultRouter
from django.urls import path, include, re_path
from .views import ProductViewSet, ProductUnitViewSet, ProductFamilyViewSet

# Create router with trailing_slash=True to ensure URLs end with a slash
router = DefaultRouter(trailing_slash=True)
router.register(r'families', ProductFamilyViewSet)  # Register specific routes first
router.register(r'product-units', ProductUnitViewSet)
router.register(r'', ProductViewSet)  # Register catch-all route last

# Create the URL patterns
urlpatterns = [
    # Add explicit paths for the ProductFamilyViewSet actions to ensure they are registered first
    path('families/add_product/', ProductFamilyViewSet.as_view({'post': 'add_product'}), name='family-add-product'),
    path('families/suggest_matches/', ProductFamilyViewSet.as_view({'post': 'suggest_matches'}), name='family-suggest-matches'),
    path('families/get_or_create/', ProductFamilyViewSet.as_view({'post': 'get_or_create'}), name='family-get-or-create'),
    
    # Include the router URLs after the explicit paths to avoid conflicts
    path('', include(router.urls)),
]
