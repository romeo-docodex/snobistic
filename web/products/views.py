from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from .models import Product, ProductImage, ProductReport
from .forms import StoreProductForm, AuctionProductForm, ProductImageFormSet
from .filters import ProductFilter


def is_shopmanager(user):
    return user.is_authenticated and user.user_type == 'shopmanager'


# ============================
# 1. LISTARE & FILTRARE
# ============================
def product_list_view(request):
    qs = Product.objects.filter(is_published=True, is_approved=True, is_active=True)
    f = ProductFilter(request.GET, queryset=qs)
    # SEO defaults for the listing page
    seo_title = "Catalog Snobistic"
    seo_description = "Răsfoiește colecția noastră de produse."
    return render(request, 'products/product_list.html', {
        'filter': f,
        'meta_title': seo_title,
        'meta_description': seo_description,
    })


# ============================
# 2. DETALII PRODUS
# ============================
def product_detail_view(request, slug):
    product = get_object_or_404(
        Product, slug=slug,
        is_published=True, is_approved=True, is_active=True
    )
    # SEO from the object, fallback to name + excerpt
    seo_title = product.meta_title or product.name
    excerpt = (product.meta_description[:157] + '…') \
        if product.meta_description else product.description[:160]
    seo_description = product.meta_description or excerpt

    return render(request, 'products/product_detail.html', {
        'product': product,
        'meta_title': seo_title,
        'meta_description': seo_description,
    })


# ============================
# 3. ADAUGĂ PRODUS (STORE)
# ============================
@login_required
def add_product_store_view(request):
    if request.method == 'POST':
        form = StoreProductForm(request.POST, request.FILES)
        formset = ProductImageFormSet(request.POST, request.FILES,
                                      queryset=ProductImage.objects.none())
        if form.is_valid() and formset.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            for img_form in formset:
                if img_form.cleaned_data and not img_form.cleaned_data.get('DELETE'):
                    img = img_form.save(commit=False)
                    img.product = product
                    img.save()
            messages.success(request, 'Produsul a fost adăugat și așteaptă validare.')
            return redirect('products:product_list')
    else:
        form = StoreProductForm()
        formset = ProductImageFormSet(queryset=ProductImage.objects.none())

    return render(request, 'products/add_product_store.html', {
        'form': form,
        'formset': formset,
        # pass SEO form fields too
    })


# ============================
# 4. ADAUGĂ PRODUS (AUCTION)
# ============================
@login_required
def add_product_auction_view(request):
    if request.method == 'POST':
        form = AuctionProductForm(request.POST, request.FILES)
        formset = ProductImageFormSet(request.POST, request.FILES,
                                      queryset=ProductImage.objects.none())
        if form.is_valid() and formset.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            for img_form in formset:
                if img_form.cleaned_data and not img_form.cleaned_data.get('DELETE'):
                    img = img_form.save(commit=False)
                    img.product = product
                    img.save()
            messages.success(request, 'Produsul a fost adăugat la licitație.')
            return redirect('products:product_list')
    else:
        form = AuctionProductForm()
        formset = ProductImageFormSet(queryset=ProductImage.objects.none())

    return render(request, 'products/add_product_auction.html', {
        'form': form,
        'formset': formset,
    })


# ============================
# 5. UPLOAD CERTIFICAT
# ============================
@login_required
def upload_proof_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user)
    if request.method == 'POST' and request.FILES.get('authenticity_proof'):
        product.authenticity_proof = request.FILES['authenticity_proof']
        product.save()
        messages.success(request, 'Fișierul a fost încărcat.')
        return redirect('products:product_detail', slug=product.slug)
    return render(request, 'products/upload_proof_of_authenticity.html', {
        'product': product
    })


# ============================
# 6. VALIDARE PENDING (SHOPMANAGER)
# ============================
@user_passes_test(is_shopmanager)
def pending_products_view(request):
    pending = Product.objects.filter(is_approved=False, is_published=False)
    return render(request, 'products/pending_products.html', {
        'pending': pending
    })


@user_passes_test(is_shopmanager)
def validate_product_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            product.is_approved = True
            product.is_published = True
            product.save()
            messages.success(request, 'Produsul a fost aprobat.')
        elif action == 'reject':
            product.is_active = False
            product.save()
            messages.warning(request, 'Produsul a fost respins.')
        return redirect('products:pending_products')
    return render(request, 'products/validate_product.html', {
        'product': product
    })


# ============================
# 7. RAPORTARE PRODUS
# ============================
@login_required
def report_product_view(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        reason = request.POST.get('reason')
        if reason:
            ProductReport.objects.create(
                product=product,
                reporter=request.user,
                reason=reason
            )
            messages.success(request, 'Produsul a fost raportat. Mulțumim!')
        return redirect('products:product_detail', slug=product.slug)
    return render(request, 'products/report_product.html', {
        'product': product
    })
