# SNOBISTIC Project Full Development Plan

## 1. Django Apps

- **accounts**: gestionează înregistrarea, autentificarea (login, logout, password reset), profiluri, 2FA și social login.
- **authentication**: încărcare imagini pentru autentificare produse fără cont, integrare API extern, generare certificat digital.
- **products**: modelare și afișare produse, categorii, filtre, SKU, imagini și flux complet de adăugare/actualizare produse.
- **auctions**: creare licitații, plasare și validare oferte, închidere automată după timp, monitorizare istoric oferte.
- **orders**: coș de cumpărături, procesare checkout, integrare plăți, gestionare comenzi, generare și upload AWB, gestionare retururi.
- **vendors**: profil vendor, dashboard vânzări și licitații, gestionare produse, cereri de plată, portofel și tranzacții.
- **customers**: profil client, istoricul comenzilor, dimensiuni salvate, wishlist, favorite, inițiere retur și chat cu vendor.
- **chat**: mesagerie sincronă și asincronă între utilizatori, chat live suport și integrare cu ticketing.
- **support**: sistem de ticketing intern, gestionare și prioritizare solicitări suport.
- **administration**: extensii pentru Django Admin, configurări platformă (comisioane, termene retur, durate licitații), gestionare roluri și permisiuni.
- **api**: endpoint-uri REST și GraphQL pentru toate funcționalitățile, autentificare și autorizare.
- **common**: utilitare, mixins, filtre template, constante și funcții helper folosite cross-app.

## 2. Models (`models.py`)
 Models (`models.py`)

### accounts/models.py
- `class User(AbstractUser)`
  - `username`, `email` (unique), `password`, `is_active`, `is_staff`, `date_joined`
- `class UserProfile(models.Model)`
  - `user` (OneToOneField to User)
  - `first_name`, `last_name`, `phone`, `date_of_birth` (DateField, null=True, blank=True),
    `is_corporate` (BooleanField, default=False), `vat_number` (CharField, max_length=32, blank=True),
    `address_line1`, `address_line2`,
    `billing_address_line1` (CharField, max_length=255, blank=True),
    `billing_address_line2` (CharField, max_length=255, blank=True),
    `city`, `postal_code`, `country`, `saved_dimensions` (JSONField)
- `class TwoFactorToken(models.Model)`
  - `user` (ForeignKey to User), `token` (CharField), `created_at` (DateTimeField), `expires_at` (DateTimeField)

### authentication/models.py
- `class AuthenticationRequest(models.Model)`
  - `email` (EmailField)
  - `images` (ImageField(upload_to='auth_requests/')) *multiple*
  - `status` (CharField, choices=[('pending','Pending'),('validated','Validated'),('rejected','Rejected')])
  - `certificate_url` (URLField, blank=True)
  - `created_at` (DateTimeField), `updated_at` (DateTimeField)

### products/models.py
- `class Category(models.Model)`
  - `name`, `slug`, `parent` (ForeignKey to self, null), `created_at`, `updated_at`
- `class SubCategory(models.Model)`
  - `name`, `slug`, `category` (ForeignKey to Category), `created_at`, `updated_at`
- `class Product(models.Model)`
  - `title`, `description`, `category` (FK Category), `subcategory` (FK SubCategory), `vendor` (FK VendorProfile), `created_at`, `updated_at`
- `class StoreProduct(Product)`
  - `price` (DecimalField), `stock` (IntegerField), `sku` (OneToOneField to SKUCode)
  - `status` (CharField, choices=[('pending','Pending'),('validated','Validated'),('rejected','Rejected')], default='pending')
  - `product_type` (CharField, choices=[('new','New'),('outlet','Outlet'),('preloved','Pre-loved')])
- `class AuctionProduct(Product)`
  - `starting_price`, `reserve_price`, `bid_increment`, `start_time`, `end_time`
  - `status` (CharField, choices=[('pending','Pending'),('validated','Validated'),('rejected','Rejected')], default='pending')
  - `product_type` (CharField, choices=[('new','New'),('outlet','Outlet'),('preloved','Pre-loved')])
- `class SKUCode(models.Model)`
  - `product` (OneToOneField to Product), `code` (CharField)
- `class Attribute(models.Model)`
  - `product` (ForeignKey to Product), `name`, `value`
- `class ProductImage(models.Model)`
  - `product` (ForeignKey to Product), `image` (ImageField), `alt_text`, `is_primary` (BooleanField)
  - **signal/Celery integration**: post-save triggers `background_remove_task(image_id)` to strip background and update image URL

### auctions/models.py
- `class Auction(models.Model)`
  - `product` (OneToOneField to AuctionProduct), `start_time`, `end_time`, `current_price`,
    `status` (CharField, choices=[('pending','Pending'),('validated','Validated'),('rejected','Rejected')], default='pending')
- `class Bid(models.Model)`
  - `auction` (ForeignKey to Auction), `user` (ForeignKey to User), `amount` (DecimalField), `timestamp` (DateTimeField)

### administration/models.py
- `class PlatformSettings(models.Model)`
  - `key` (CharField), `value` (JSONField), `description`
  - `return_days` (IntegerField)  
  - `shipping_days` (IntegerField)  # număr zile pentru expediere înainte de anulare AWB
- `class Role(models.Model)`
  - `name` (CharField), `permissions` (ManyToManyField to django.contrib.auth.models.Permission)

## 3. Views (`views.py`)

### accounts/views.py
- `login_view(request)`
- `logout_view(request)`
- `register_view(request)`
- `profile_view(request)`
- `two_factor_verify_view(request)`
- `password_reset_view(request)`
- `password_reset_confirm_view(request, uidb64, token)`
- `social_login_google(request)`
- `social_login_facebook(request)`
- `social_login_apple(request)`

### products/views.py
- `product_list_view(request)`
- `product_detail_view(request, pk)`
- `product_add_step1_view(request)`
- `product_add_step2_view(request)`
- `product_add_step3_view(request)`
- `product_add_step4_view(request)`
- `product_add_step5_view(request)`
- `product_add_step6_view(request)`
- `product_edit_view(request, pk)`
- `product_delete_view(request, pk)`
- `submit_to_auction_view(request, pk)`

### auctions/views.py
- `auction_list_view(request)`
- `auction_detail_view(request, pk)`
- `place_bid_view(request, auction_id)`
- `auction_status_view(request, auction_id)`
- `close_auction_task()` (Celery task)

### orders/views.py
- `cart_view(request)`
- `add_to_cart_view(request, product_id)`
- `remove_from_cart_view(request, cart_item_id)`
- `checkout_view(request)`
- `order_list_view(request)`
- `order_detail_view(request, order_id)`
- `payment_success_view(request, order_id)`
- `payment_failure_view(request, order_id)`
- `generate_awb_view(request, order_id)`
- `upload_awb_images_view(request, shipment_id)`
- `confirm_shipment_view(request, shipment_id)`
- `return_request_view(request, order_id)`

### vendors/views.py
- `vendor_dashboard_view(request)`
- `vendor_products_posted_view(request)`
- `vendor_auctions_posted_view(request)`
- `vendor_sold_items_view(request)`
- `vendor_account_view(request)`
- `sku_code_generation_view(request)`
- `export_products_csv_view(request)`
- `payout_request_view(request)`
- `wallet_history_view(request)`
- `generate_wallet_statement_view(request, period)`

### customers/views.py
- `customer_account_view(request)`
- `saved_dimensions_view(request)`
- `wishlist_view(request)`
- `favorites_view(request)`
- `order_history_view(request)`
- `order_detail_view(request, order_id)`
- `return_view(request, order_id)`
- `chat_with_vendor_view(request, vendor_id)`

### chat/views.py
- `conversation_list_view(request)`
- `message_create_view(request, conversation_id)`
- `live_chat_queue_view(request)`
- `support_ticket_redirect_email_view(request, ticket_id)`

### support/views.py
- `ticket_list_view(request)`
- `ticket_detail_view(request, ticket_id)`
- `ticket_response_view(request, ticket_id)`

### administration/views.py
- `settings_view(request)`
- `commission_settings_view(request)`
- `return_days_settings_view(request)`
- `shipping_deadline_settings_view(request)`
- `auction_duration_settings_view(request)`
- `role_management_view(request)`
- `validate_post_view(request, product_id)`
- `admin_chat_view(request)`

### api/views.py (Django REST Framework)
- `UserViewSet` (list, retrieve, create, update, delete)
- `ProductViewSet` (list, retrieve, create, update, delete)
- `AuctionViewSet` (list, retrieve, place_bid)
- `CartView` (retrieve, update)
- `OrderViewSet` (list, retrieve, create)
- `VendorDashboardAPIView`
- `CustomerProfileAPIView`
- `ConversationAPIView`
- `TicketAPIView`
- `PlatformSettingsAPIView`

## 4. URL Configuration (`urls.py`)

### project/urls.py
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('auctions/', include('auctions.urls')),
    path('cart/', include('orders.urls')),
    path('vendors/', include('vendors.urls')),
    path('customers/', include('customers.urls')),
    path('chat/', include('chat.urls')),
    path('support/', include('support.urls')),
    path('admin-panel/', include('administration.urls')),
    path('api/', include('api.urls')),
]
````

### accounts/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('2fa/', views.two_factor_verify_view, name='two_factor_verify'),
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('social/google/', views.social_login_google, name='social_google'),
    path('social/facebook/', views.social_login_facebook, name='social_facebook'),
    path('social/apple/', views.social_login_apple, name='social_apple'),
]
```

### products/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list_view, name='product_list'),
    path('<int:pk>/', views.product_detail_view, name='product_detail'),
    path('add/step-1/', views.product_add_step1_view, name='product_add_step1'),
    path('add/step-2/', views.product_add_step2_view, name='product_add_step2'),
    path('add/step-3/', views.product_add_step3_view, name='product_add_step3'),
    path('add/step-4/', views.product_add_step4_view, name='product_add_step4'),
    path('add/step-5/', views.product_add_step5_view, name='product_add_step5'),
    path('add/step-6/', views.product_add_step6_view, name='product_add_step6'),
    path('<int:pk>/edit/', views.product_edit_view, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete_view, name='product_delete'),
    path('<int:pk>/auction/', views.submit_to_auction_view, name='submit_to_auction'),
]
```

### auctions/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.auction_list_view, name='auction_list'),
    path('<int:pk>/', views.auction_detail_view, name='auction_detail'),
    path('<int:auction_id>/bid/', views.place_bid_view, name='place_bid'),
    path('<int:auction_id>/status/', views.auction_status_view, name='auction_status'),
]
```

### orders/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_view, name='cart'),
    path('add/<int:product_id>/', views.add_to_cart_view, name='add_to_cart'),
    path('remove/<int:cart_item_id>/', views.remove_from_cart_view, name='remove_from_cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('orders/', views.order_list_view, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('payment-success/<int:order_id>/', views.payment_success_view, name='payment_success'),
    path('payment-failure/<int:order_id>/', views.payment_failure_view, name='payment_failure'),
    path('shipment/<int:order_id>/generate-awb/', views.generate_awb_view, name='generate_awb'),
    path('shipment/<int:shipment_id>/upload-awb/', views.upload_awb_images_view, name='upload_awb'),
    path('shipment/<int:shipment_id>/confirm/', views.confirm_shipment_view, name='confirm_shipment'),
    path('return/<int:order_id>/', views.return_request_view, name='return_request'),
]
```

### vendors/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.vendor_dashboard_view, name='vendor_dashboard'),
    path('products/', views.vendor_products_posted_view, name='vendor_products'),
    path('auctions/', views.vendor_auctions_posted_view, name='vendor_auctions'),
    path('sold/', views.vendor_sold_items_view, name='vendor_sold'),
    path('account/', views.vendor_account_view, name='vendor_account'),
    path('sku/generate/', views.sku_code_generation_view, name='sku_generation'),
    path('export-csv/', views.export_products_csv_view, name='export_csv'),
    path('payout-request/', views.payout_request_view, name='payout_request'),
    path('wallet-history/', views.wallet_history_view, name='wallet_history'),
    path('wallet-statement/<str:period>/', views.generate_wallet_statement_view, name='wallet_statement'),
]
```

### customers/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_account_view, name='customer_account'),
    path('dimensions/', views.saved_dimensions_view, name='saved_dimensions'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('favorites/', views.favorites_view, name='favorites'),
    path('orders/', views.order_history_view, name='customer_orders'),
    path('orders/<int:order_id>/', views.order_detail_view, name='customer_order_detail'),
    path('return/<int:order_id>/', views.return_view, name='customer_return'),
    path('chat/<int:vendor_id>/', views.chat_with_vendor_view, name='chat_with_vendor'),
]
```

### chat/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.conversation_list_view, name='conversations'),
    path('<int:conversation_id>/message/', views.message_create_view, name='send_message'),
    path('live-queue/', views.live_chat_queue_view, name='live_chat'),
    path('support-redirect/<int:ticket_id>/', views.support_ticket_redirect_email_view, name='support_redirect'),
]
```

### support/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ticket_list_view, name='tickets'),
    path('<int:ticket_id>/', views.ticket_detail_view, name='ticket_detail'),
    path('<int:ticket_id>/respond/', views.ticket_response_view, name='ticket_respond'),
]
```

### administration/urls.py

```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.settings_view, name='admin_settings'),
    path('commissions/', views.commission_settings_view, name='commission_settings'),
    path('returns/', views.return_days_settings_view, name='return_days_settings'),
    path('shipping-deadline/', views.shipping_deadline_settings_view, name='shipping_deadline_settings'),
    path('auction-duration/', views.auction_duration_settings_view, name='auction_duration_settings'),
    path('roles/', views.role_management_view, name='role_management'),
    path('validate/<int:product_id>/', views.validate_post_view, name='validate_post'),
    path('chat/', views.admin_chat_view, name='admin_chat'),
]
```

### api/urls.py

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'auctions', views.AuctionViewSet)
router.register(r'orders', views.OrderViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('cart/', views.CartView.as_view(), name='api_cart'),
    path('vendor-dashboard/', views.VendorDashboardAPIView.as_view(), name='api_vendor_dashboard'),
    path('customer-profile/', views.CustomerProfileAPIView.as_view(), name='api_customer_profile'),
    path('conversations/', views.ConversationAPIView.as_view(), name='api_conversations'),
    path('tickets/', views.TicketAPIView.as_view(), name='api_tickets'),
    path('settings/', views.PlatformSettingsAPIView.as_view(), name='api_settings'),
]
```

## 5. Templates (`templates/`)

```
templates/
├── base.html
├── accounts/
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── 2fa_verify.html
│   ├── password_reset.html
│   └── password_reset_confirm.html
├── products/
│   ├── product_list.html          # afișare listă produse
│   ├── product_detail.html        # detalii produs
│   ├── add_step1.html             # adăugare produs - pas 1: informații generale
│   ├── add_step2.html             # adăugare produs - pas 2: dimensiuni preset
│   ├── add_step3.html             # adăugare produs - pas 3: dimensiuni custom
│   ├── add_step4.html             # adăugare produs - pas 4: material
│   ├── add_step5.html             # adăugare produs - pas 5: descriere
│   ├── add_step6.html             # adăugare produs - pas 6: preț / setări licitație
│   └── product_form.html          # formulare reutilizabile add/edit
├── auctions/
│   ├── auction_list.html          # listă licitații active
│   ├── auction_detail.html        # detalii licitație
│   └── bid_form.html              # formular plasare ofertă
├── orders/
│   ├── cart.html                  # vedere și modificare coș
│   ├── checkout.html              # pagină checkout
│   ├── order_list.html            # listă comenzi client
│   ├── order_detail.html          # detalii comandă
│   └── return_request.html        # formular cerere retur
├── vendors/
│   ├── dashboard.html             # dashboard vendor
│   ├── products_posted.html       # produse afișate
│   ├── auctions_posted.html       # licitații create
│   ├── sold_items.html            # istoricul vânzări
│   ├── account.html               # setări cont vendor
│   └── export_csv.html            # export CSV produse
├── customers/
│   ├── account.html               # dashboard client
│   ├── saved_dimensions.html      # dimensiuni salvate
│   ├── wishlist.html              # lista de dorințe
│   ├── favorites.html             # favorite
│   └── orders.html                # listă comenzi client
├── chat/
│   ├── conversation_list.html     # listă conversații
│   └── conversation.html          # chat view
├── support/
│   ├── ticket_list.html           # listă tichete
│   └── ticket_detail.html         # detalii tichet
└── administration/
    ├── settings.html              # setări generale platformă
    ├── commission_settings.html   # configurare comisioane
    ├── return_days.html           # configurare zile retur
    ├── shipping_deadline.html     # configurare termene shipping
    ├── auction_duration.html      # configurare durată licitație
    └── validate_post.html         # pagină validare produs
```

În `base.html` includem blocurile standard (`{% block title %}`, `{% block content %}`, `{% block scripts %}`) și navbar/footer comuni.

## 6. APIs (`api/`)

Se folosește **Django REST Framework** pentru endpoint-uri JSON/REST și **Graphene-Django** pentru GraphQL.

### Serializers (`api/serializers.py`)

* `UserSerializer` (User model, câmpuri: id, username, email, first\_name, last\_name)
* `RegisterSerializer` (creare cont cu password write\_only)
* `LoginSerializer` (email, password)
* `TwoFactorSerializer` (token)
* `CategorySerializer`, `SubCategorySerializer`
* `ProductSerializer` (Serializare Product, incl. `StoreProductSerializer`, `AuctionProductSerializer`)
* `SKUCodeSerializer`
* `AttributeSerializer`, `ProductImageSerializer`
* `AuctionSerializer` (Auction model, nested Product)
* `BidSerializer` (Bid model)
* `CartSerializer` (Cart + CartItem nested)
* `OrderSerializer`, `OrderItemSerializer`
* `PaymentSerializer`
* `ShipmentSerializer`
* `ReturnRequestSerializer`
* `VendorProfileSerializer`, `WalletTransactionSerializer`, `CommissionInvoiceSerializer`
* `CustomerProfileSerializer`, `SavedDimensionSerializer`, `WishlistSerializer`, `FavoriteSerializer`
* `ConversationSerializer`, `MessageSerializer`
* `TicketSerializer`, `TicketMessageSerializer`
* `PlatformSettingsSerializer`, `RoleSerializer`

### ViewSets & Views (`api/views.py`)

```python
from rest_framework import viewsets, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    @action(detail=False, methods=['post'])
    def register(self, request): ...
    @action(detail=False, methods=['post'])
    def login(self, request): ...
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def two_factor(self, request): ...

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ['category', 'subcategory', 'vendor']

class AuctionViewSet(viewsets.ModelViewSet):
    queryset = Auction.objects.all()
    serializer_class = AuctionSerializer
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def place_bid(self, request, pk=None): ...

class CartView(generics.RetrieveUpdateAPIView):
    serializer_class = CartSerializer
    def get_object(self): return self.request.user.cart

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    def perform_create(self, serializer): ...

class VendorDashboardAPIView(generics.RetrieveAPIView):
    serializer_class = VendorProfileSerializer
    def get_object(self): return self.request.user.vendorprofile

class CustomerProfileAPIView(generics.RetrieveAPIView):
    serializer_class = CustomerProfileSerializer
    def get_object(self): return self.request.user.customerprofile

class ConversationAPIView(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    def get_queryset(self): return Conversation.objects.filter(participants=self.request.user)

class MessageAPIView(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

class TicketAPIView(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None): ...

class PlatformSettingsAPIView(generics.ListCreateAPIView):
    queryset = PlatformSettings.objects.all()
    serializer_class = PlatformSettingsSerializer
```

### Endpoints (`api/urls.py`)

```text
POST    /api/users/register/            # înregistrare cont
POST    /api/users/login/               # autentificare
POST    /api/users/two_factor/          # validare 2FA
GET     /api/users/                     # listare utilizatori (admin)
GET     /api/users/{id}/                # detalii utilizator

GET,POST,PUT,DELETE /api/products/      # CRUD produse
GET     /api/products/{id}/             # detalii produs

GET,POST,PUT,DELETE /api/auctions/      # CRUD licitații
POST    /api/auctions/{id}/place_bid/   # plasare ofertă

GET,PUT    /api/cart/                   # vizualizare / actualizare coș

GET,POST    /api/orders/                # creare / listare comenzi
GET         /api/orders/{id}/           # detalii comandă

GET     /api/vendor-dashboard/         # date dashboard vendor
GET     /api/customer-profile/         # date profil client

GET     /api/conversations/            # listă conversații
POST    /api/conversations/            # creare conversație
GET     /api/conversations/{id}/       # detalii conversație
GET,POST    /api/messages/             # mesaje chat

GET,POST,PUT,DELETE /api/tickets/      # CRUD tichete suport
POST    /api/tickets/{id}/respond/     # răspuns tichet

GET,POST      /api/settings/            # citire / actualizare setări platformă

# GraphQL endpoint:
POST    /api/graphql/                   # interogări și mutații GraphQL (schema configurată în schema.py)
```

## 7. Static & Media

### Structură directoare

```
static/
├── css/
│   ├── base.scss
│   ├── accounts.scss
│   ├── products.scss
│   ├── auctions.scss
│   ├── orders.scss
│   ├── vendors.scss
│   ├── customers.scss
│   ├── chat.scss
│   ├── support.scss
│   ├── administration.scss
│   └── common.scss
├── js/
│   ├── accounts.js
│   ├── products.js
│   ├── auctions.js
│   ├── cart.js
│   ├── vendors.js
│   ├── customers.js
│   ├── chat.js
│   ├── support.js
│   ├── administration.js
│   └── common.js
└── images/
    ├── logo.svg
    ├── banner.jpg
    └── placeholders/
        ├── product_placeholder.png
        └── avatar_placeholder.png

media/
├── products/
│   └── <product_id>/<filename>
├── profiles/
│   └── <user_id>/<filename>
└── awb_labels/
    └── <shipment_id>/<filename>
```

### Setări Django

```python
# settings.py
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Folosim django-storages dacă vrem S3 sau alt bucket
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

### Compilare & Management

* Folosim **django-compressor** pentru minificare CSS/JS
* Task Celery zilnic pentru curățare media neutilizate

## 8. Celery Tasks

Pendinte de configurare **Celery + Redis**:

* **tasks/auction.py**

  * `@shared_task
    def close_auction(auction_id):`
    Închide licitația la `end_time`, actualizează status, notifică câștigătorul și vendorul.
  * `@periodic_task(run_every=crontab(minute='*/1'))
    def check_auctions():`
    Verifică licitațiile care s-au încheiat și apelează `close_auction`.

* **tasks/notifications.py**

  * `@shared_task
    def send_email_notification(user_id, subject, message):`
    Trimite email provenit din sisteme de evenimente.
  * `@shared_task
    def send_sms_notification(phone, message):`
    Trimite SMS prin API-ul configurat.

* **tasks/cleanup.py**

  * `@periodic_task(run_every=crontab(hour=0, minute=0))
    def clean_expired_carts():`
    Șterge coșuri inactive de peste 30 zile.
  * `@periodic_task(run_every=crontab(hour='*/6'))
    def clean_stale_bids():`
    Șterge oferte în așteptare expirate.
  * `@periodic_task(run_every=crontab(hour=1, minute=0))
    def clean_unused_media():`
    Elimină fișiere media nelegate de nicio intrare.

* **tasks/integrations.py**

  * `@shared_task
    def generate_awb(order_id):`
    Apelează API curier, salvează AWB.
  * `@shared_task
    def fetch_exchange_rates():`
    Pentru conversia valutară.

## 9. Permissions & Roles

### Roluri și Grupuri

* `Role` model (`administration.models.Role`)

  * Câmpuri: `name`, `permissions` (ManyToMany la `auth.Permission`)
  * Roluri presetate: `Admin`, `ShopManager`, `Vendor`, `Customer`, `SupportAgent`
* Grups Django (`auth.Group`)

  * Mapare 1:1 cu `Role`, sincronizate în semnal `post_save` Role -> Group

### Permisiuni Custom

* Definite în meta clasă pentru fiecare model, ex:

  ```python
  class Product(models.Model):
      class Meta:
          permissions = [
              ('view_unpublished_product', 'Can view unpublished product'),
              ('approve_product', 'Can approve product for listing'),
          ]
  ```
* Exemple permisiuni:

  * `can_view_all_orders`, `can_manage_orders`
  * `can_generate_awb`, `can_upload_awb`
  * `can_view_vendor_dashboard`, `can_edit_vendor_profile`
  * `can_manage_auctions`, `can_close_auctions`
  * `can_manage_support_tickets` (pentru agenți support)

### Monitorizare Acces

* Utilizare mixin-uri și decorațiuni:

  * `@permission_required('products.approve_product')`
  * `class VendorRequiredMixin(UserPassesTestMixin):`
* Control acces în vizualizări CBV:

  ```python
  class AuctionListView(PermissionRequiredMixin, ListView):
      permission_required = 'auctions.view_auction'
  ```

### UI pentru Roluri

* Pagina de administrare roluri și permisiuni (`administration/views.py`):

  * Grid cu roluri, permisiuni disponibile, buton de asignare