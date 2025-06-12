import django_filters
from .models import Product, Category, Brand


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', label='Caută după nume')
    brand = django_filters.ModelChoiceFilter(queryset=Brand.objects.all())
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.all())
    price__gt = django_filters.NumberFilter(
        field_name='price', lookup_expr='gte', label='Preț minim'
    )
    price__lt = django_filters.NumberFilter(
        field_name='price', lookup_expr='lte', label='Preț maxim'
    )
    stock__gt = django_filters.NumberFilter(
        field_name='stock', lookup_expr='gte', label='Stoc minim'
    )
    stock__lt = django_filters.NumberFilter(
        field_name='stock', lookup_expr='lte', label='Stoc maxim'
    )
    condition = django_filters.ChoiceFilter(choices=Product.CONDITION_CHOICES)

    class Meta:
        model = Product
        fields = [
            'name', 'brand', 'category',
            'condition', 'price__gt', 'price__lt',
            'stock__gt', 'stock__lt'
        ]
