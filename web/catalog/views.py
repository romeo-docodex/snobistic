# catalog/views.py
from decimal import Decimal

from django.db.models import Q, Min, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.decorators.http import require_GET

from django.views.generic import (
    ListView,
    DetailView,
    TemplateView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .forms import SearchForm, ProductForm
from .models import (
    Product,
    Category,
    Subcategory,
    Material,
    Favorite,
    Color,
    ProductImage,
    Brand,
    ProductMaterial,
    SustainabilityTag,
)

FAV_SESSION_KEY = "favorites"
RECENTLY_VIEWED_SESSION_KEY = "recently_viewed_products"


def _get_session_favorites(request):
    raw = request.session.get(FAV_SESSION_KEY, [])
    try:
        ids = [int(x) for x in raw]
    except (TypeError, ValueError):
        ids = []
    seen = set()
    ids = [x for x in ids if not (x in seen or seen.add(x))]
    return ids


def _get_recently_viewed(request):
    raw = request.session.get(RECENTLY_VIEWED_SESSION_KEY, [])
    try:
        ids = [int(x) for x in raw]
    except (TypeError, ValueError):
        ids = []
    # eliminăm duplicatele, păstrând ordinea
    seen = set()
    ids = [x for x in ids if not (x in seen or seen.add(x))]
    return ids


def _save_recently_viewed(request, product_id, max_items=20):
    """
    Adaugă produsul în lista de 'văzute recent' din sesiune.
    Păstrăm maxim max_items, fără dubluri.
    """
    ids = _get_recently_viewed(request)
    # scoatem dacă există deja
    ids = [x for x in ids if x != product_id]
    # adăugăm la final ca „cel mai recent”
    ids.append(product_id)
    # limităm la max_items (cele mai recente la final)
    if len(ids) > max_items:
        ids = ids[-max_items:]

    request.session[RECENTLY_VIEWED_SESSION_KEY] = ids
    request.session.modified = True


def _save_session_favorites(request, ids):
    request.session[FAV_SESSION_KEY] = ids
    request.session.modified = True
    request.session.set_expiry(60 * 60 * 24 * 30)


@require_GET
def ajax_subcategories(request):
    """
    Returnează subcategoriile pentru o categorie root dată,
    ca JSON: {results: [{id, name}, ...]}

    Parametri GET:
    - parent_id = id-ul categoriei principale (Category.id)
    - gender    = 'F' sau 'M' (opțional); dacă e setat, filtrăm
                  subcategoriile compatibile cu genul respectiv.
    """
    parent_id = request.GET.get("parent_id")
    try:
        parent_id = int(parent_id)
    except (TypeError, ValueError):
        return JsonResponse({"results": []})

    subcats = Subcategory.objects.filter(category_id=parent_id)

    gender = request.GET.get("gender")
    if gender in ("F", "M"):
        # replicăm logica Subcategory.allows_gender:
        subcats = subcats.filter(
            Q(gender__isnull=True)
            | Q(gender="")
            | Q(gender="U")
            | Q(gender=gender)
        )

    subcats = subcats.order_by("name")
    data = [{"id": c.id, "name": c.name} for c in subcats]
    return JsonResponse({"results": data})


def toggle_favorite(request, pk):
    pk = int(pk)

    # permitem orice produs activ/ne-arhivat, indiferent de status/moderare
    _ = get_object_or_404(
        Product,
        pk=pk,
        is_active=True,
        is_archived=False,
    )

    if request.user.is_authenticated:
        qs = Favorite.objects.filter(user=request.user, product_id=pk)
        if qs.exists():
            qs.delete()
            added = False
        else:
            Favorite.objects.create(user=request.user, product_id=pk)
            added = True

        count = Favorite.objects.filter(user=request.user).count()

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "added": added, "count": count})

        return redirect(
            request.META.get("HTTP_REFERER")
            or reverse("catalog:product_list")
        )

    favs = _get_session_favorites(request)
    added = False
    if pk in favs:
        favs = [x for x in favs if x != pk]
    else:
        favs.append(pk)
        added = True

    _save_session_favorites(request, favs)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "added": added, "count": len(favs)})

    return redirect(
        request.META.get("HTTP_REFERER")
        or reverse("catalog:product_list")
    )


class ProductListView(ListView):
    model = Product
    template_name = "catalog/product_list.html"
    context_object_name = "products"
    paginate_by = 20

    def get_queryset(self):
        # listă de bază: produse active, ne-arhivate, cu status moderare OK
        qs = Product.objects.filter(
            is_active=True,
            is_archived=False,
            moderation_status__in=["APPROVED", "PUBLISHED"],
        )

        g = self.request.GET

        # === Căutare generală (q) ===
        term = (g.get("q") or "").strip()
        if term:
            qs = qs.filter(
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(sku__icontains=term)
                | Q(brand__name__icontains=term)
                | Q(brand_other__icontains=term)
                | Q(category__name__icontains=term)
                | Q(subcategory__name__icontains=term)
                | Q(real_color_name__icontains=term)
            )

        # === Categorie (radio) – slug din querystring ===
        category_slug = (g.get("category") or "").strip()
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        # === Preț ===
        min_price = g.get("min_price")
        max_price = g.get("max_price")
        if min_price:
            try:
                qs = qs.filter(price__gte=Decimal(str(min_price)))
            except (TypeError, ValueError):
                pass
        if max_price:
            try:
                qs = qs.filter(price__lte=Decimal(str(max_price)))
            except (TypeError, ValueError):
                pass

        # === Mărime (legacy) – câmpul `size` ===
        sizes = g.getlist("size")
        if sizes:
            qs = qs.filter(size__in=sizes)

        # === Mărimi noi ===
        size_alpha_list = g.getlist("size_alpha")
        if size_alpha_list:
            qs = qs.filter(size_alpha__in=size_alpha_list)

        size_fr_list = [int(x) for x in g.getlist("size_fr") if x.isdigit()]
        if size_fr_list:
            qs = qs.filter(size_fr__in=size_fr_list)

        size_it_list = [int(x) for x in g.getlist("size_it") if x.isdigit()]
        if size_it_list:
            qs = qs.filter(size_it__in=size_it_list)

        size_gb_list = [int(x) for x in g.getlist("size_gb") if x.isdigit()]
        if size_gb_list:
            qs = qs.filter(size_gb__in=size_gb_list)

        shoe_size_vals = []
        for raw in g.getlist("shoe_size_eu"):
            try:
                shoe_size_vals.append(Decimal(str(raw)))
            except (TypeError, ValueError):
                continue
        if shoe_size_vals:
            qs = qs.filter(shoe_size_eu__in=shoe_size_vals)

        # === Brand (multi, id) ===
        brand_ids = [int(x) for x in g.getlist("brand") if x.isdigit()]
        if brand_ids:
            qs = qs.filter(brand_id__in=brand_ids)

        # === Material (multi, id) – material principal + compoziții M2M ===
        material_ids = [int(x) for x in g.getlist("material") if x.isdigit()]
        if material_ids:
            qs = qs.filter(
                Q(material_id__in=material_ids)
                | Q(compositions__material_id__in=material_ids)
            ).distinct()

        # === Culoare (multi, id) – base_color + colors M2M ===
        color_ids = [int(x) for x in g.getlist("color") if x.isdigit()]
        if color_ids:
            qs = qs.filter(
                Q(base_color_id__in=color_ids)
                | Q(colors__id__in=color_ids)
            ).distinct()

        # === Condiție (multi) ===
        conditions = g.getlist("condition")
        if conditions:
            qs = qs.filter(condition__in=conditions)

        # === Gen (single) ===
        gender = g.get("gender")
        if gender:
            qs = qs.filter(gender=gender)

        # === Croi (multi) ===
        fits = g.getlist("fit")
        if fits:
            qs = qs.filter(fit__in=fits)

        # === Sustenabilitate ===
        sustainability_keys = [k for k in g.getlist("sustainability") if k]
        if sustainability_keys:
            sust_q = Q()
            if "NONE" in sustainability_keys:
                sust_q |= Q(sustainability_none=True)
                sustainability_keys = [k for k in sustainability_keys if k != "NONE"]

            if sustainability_keys:
                sust_q |= Q(sustainability_tags__key__in=sustainability_keys)

            if sust_q:
                qs = qs.filter(sust_q).distinct()

        # === Dimensiuni (cm) – interval dim_min / dim_max pe câmpurile *_cm ===
        dim_min_raw = g.get("dim_min")
        dim_max_raw = g.get("dim_max")
        dim_min = dim_max = None

        try:
            if dim_min_raw not in (None, ""):
                dim_min = int(dim_min_raw)
        except (TypeError, ValueError):
            dim_min = None

        try:
            if dim_max_raw not in (None, ""):
                dim_max = int(dim_max_raw)
        except (TypeError, ValueError):
            dim_max = None

        if dim_min is not None or dim_max is not None:
            dim_fields = [
                # îmbrăcăminte
                "shoulders_cm",
                "bust_cm",
                "waist_cm",
                "hips_cm",
                "length_cm",
                "sleeve_cm",
                "inseam_cm",
                "outseam_cm",
                # încălțăminte
                "shoe_insole_length_cm",
                "shoe_width_cm",
                "shoe_heel_height_cm",
                "shoe_total_height_cm",
                # genți
                "bag_width_cm",
                "bag_height_cm",
                "bag_depth_cm",
                "strap_length_cm",
                # curele
                "belt_length_total_cm",
                "belt_length_usable_cm",
                "belt_width_cm",
                # bijuterii / accesorii
                "jewelry_chain_length_cm",
                "jewelry_drop_length_cm",
                "jewelry_pendant_size_cm",
            ]
            dim_q = Q()
            for field in dim_fields:
                field_filters = {}
                if dim_min is not None:
                    field_filters[f"{field}__gte"] = dim_min
                if dim_max is not None:
                    field_filters[f"{field}__lte"] = dim_max
                if field_filters:
                    dim_q |= Q(**field_filters)

            if dim_q:
                qs = qs.filter(dim_q)

        # === Disponibilitate (dacă vei adăuga checkbox / select în UI) ===
        availability = g.get("availability")
        if availability == "in":
            qs = qs.filter(is_active=True, is_archived=False)
        elif availability == "out":
            qs = qs.filter(Q(is_active=False) | Q(is_archived=True))

        # === Sortare ===
        sort = g.get("sort")
        if sort == "a-z":
            qs = qs.order_by("title")
        elif sort == "z-a":
            qs = qs.order_by("-title")
        elif sort == "price-low-high":
            qs = qs.order_by("price")
        elif sort == "price-high-low":
            qs = qs.order_by("-price")
        else:
            # implicit: cele mai noi primele
            qs = qs.order_by("-created_at")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        g = self.request.GET

        # preț minim / maxim din toată baza de date (produse active, ne-arhivate)
        price_agg = Product.objects.filter(
            is_active=True,
            is_archived=False,
        ).aggregate(
            min_price_db=Min("price"),
            max_price_db=Max("price"),
        )

        price_min_global = price_agg["min_price_db"] or Decimal("0")
        price_max_global = price_agg["max_price_db"] or Decimal("0")

        ctx.update(
            {
                "root_categories": Category.objects.all().order_by("name"),
                "sizes": [c[0] for c in Product.SIZE_CHOICES],
                "materials": Material.objects.all(),
                "colors": Color.objects.all(),
                "brands": Brand.objects.filter(is_visible_public=True),
                "condition_choices": Product.CONDITION_CHOICES,
                "fit_choices": Product.FIT_CHOICES,
                "sustainability_tags": SustainabilityTag.objects.all().order_by("name"),
                # selectate din querystring
                "selected_category_slug": g.get("category", "") or "",
                "selected_sizes": g.getlist("size"),
                "selected_size_alpha": g.getlist("size_alpha"),
                "selected_size_fr": [
                    int(x) for x in g.getlist("size_fr") if x.isdigit()
                ],
                "selected_size_it": [
                    int(x) for x in g.getlist("size_it") if x.isdigit()
                ],
                "selected_size_gb": [
                    int(x) for x in g.getlist("size_gb") if x.isdigit()
                ],
                "selected_shoe_size_eu": g.getlist("shoe_size_eu"),
                "selected_brands": [
                    int(x) for x in g.getlist("brand") if x.isdigit()
                ],
                "selected_materials": [
                    int(x) for x in g.getlist("material") if x.isdigit()
                ],
                "selected_colors": [
                    int(x) for x in g.getlist("color") if x.isdigit()
                ],
                "selected_conditions": g.getlist("condition"),
                "selected_gender": g.get("gender") or "",
                "selected_fits": g.getlist("fit"),
                "selected_sustainability_keys": g.getlist("sustainability"),
                "min_price": g.get("min_price", ""),
                "max_price": g.get("max_price", ""),
                # prețuri globale
                "price_min_global": price_min_global,
                "price_max_global": price_max_global,
            }
        )

        user = self.request.user
        if user.is_authenticated:
            fav_ids = Favorite.objects.filter(user=user).values_list(
                "product_id", flat=True
            )
            ctx["favorite_ids"] = set(fav_ids)
        else:
            ctx["favorite_ids"] = set(_get_session_favorites(self.request))
        return ctx


class CategoryListView(ProductListView):
    """
    Listare produse pentru o categorie principală (Haine, Pantofi etc.).
    """

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"])
        base_qs = super().get_queryset()
        # toate produsele care aparțin acestei categorii (indiferent de subcategorie)
        return base_qs.filter(category=self.category)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.category
        # pentru compatibilitate cu template-uri existente care foloseau 'subcategory'
        ctx["subcategory"] = self.category
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = "catalog/product_detail.html"
    context_object_name = "product"

    def get_object(self):
        # permitem orice produs activ/ne-arhivat (indiferent de moderare / sale_type)
        return get_object_or_404(
            Product,
            slug=self.kwargs["slug"],
            is_active=True,
            is_archived=False,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        user = request.user
        product = self.object

        # este owner-ul produsului?
        is_owner = user.is_authenticated and (product.owner == user)
        ctx["is_owner"] = is_owner

        # licitația aferentă produsului, dacă există (OneToOneField related_name='auction')
        auction = getattr(product, "auction", None)
        ctx["auction"] = auction
        ctx["has_auction"] = auction is not None

        # poate porni licitație DOAR owner-ul,
        # DOAR dacă produsul este FIXED și NU are deja licitație
        can_start_auction = (
            is_owner
            and getattr(product, "sale_type", "") == "FIXED"
            and auction is None
        )
        ctx["can_start_auction"] = can_start_auction

        # Favorite
        if user.is_authenticated:
            fav_ids = Favorite.objects.filter(user=user).values_list(
                "product_id", flat=True
            )
            ctx["favorite_ids"] = set(fav_ids)
        else:
            favs = _get_session_favorites(request)
            ctx["favorite_ids"] = set(favs)

        # === RELATED PRODUCTS ===
        related_qs = Product.objects.filter(
            is_active=True,
            is_archived=False,
        ).exclude(pk=product.pk)

        # prioritar pe subcategorie, altfel pe categorie
        if product.subcategory_id:
            related_qs = related_qs.filter(subcategory_id=product.subcategory_id)
        else:
            related_qs = related_qs.filter(category_id=product.category_id)

        related_products = list(related_qs.order_by("-created_at")[:12])
        ctx["related_products"] = related_products

        # === RECENTLY VIEWED ===
        _save_recently_viewed(request, product.pk, max_items=20)
        ids = _get_recently_viewed(request)
        ids = [pk for pk in ids if pk != product.pk]

        if ids:
            rv_qs = Product.objects.filter(
                pk__in=ids,
                is_active=True,
                is_archived=False,
            )
            order = {pid: i for i, pid in enumerate(reversed(ids))}
            recently_viewed = sorted(
                rv_qs,
                key=lambda p: order.get(p.pk, 0),
            )
        else:
            recently_viewed = []

        ctx["recently_viewed"] = recently_viewed

        # impact CO₂ (din subcategorie, cu fallback pentru „Alt tip de …”)
        impact_avg, impact_co2, impact_trees = product.get_subcategory_impact()
        ctx["avg_weight_kg"] = impact_avg
        ctx["co2_avoided_kg"] = impact_co2
        ctx["trees_equivalent"] = impact_trees
        ctx["has_subcategory_impact"] = product.subcategory_has_impact_data

        return ctx


class SearchResultsView(ListView):
    model = Product
    template_name = "catalog/search_results.html"
    context_object_name = "products"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        self.form = SearchForm(request.GET)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # căutăm în toate produsele active, ne-arhivate
        qs = Product.objects.filter(
            is_active=True,
            is_archived=False,
        )
        if self.form.is_valid():
            term = self.form.cleaned_data["q"]
            qs = qs.filter(
                Q(title__icontains=term)
                | Q(description__icontains=term)
                | Q(sku__icontains=term)
                | Q(brand__name__icontains=term)
                | Q(brand_other__icontains=term)
                | Q(category__name__icontains=term)
                | Q(subcategory__name__icontains=term)
                | Q(owner__email__icontains=term)
                | Q(owner__first_name__icontains=term)
                | Q(owner__last_name__icontains=term)
                | Q(real_color_name__icontains=term)
            )
        else:
            qs = qs.none()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_term"] = self.request.GET.get("q", "")
        ctx["root_categories"] = Category.objects.all().order_by("name")

        user = self.request.user
        if user.is_authenticated:
            fav_ids = Favorite.objects.filter(user=user).values_list(
                "product_id", flat=True
            )
            ctx["favorite_ids"] = set(fav_ids)
        else:
            ctx["favorite_ids"] = set(_get_session_favorites(self.request))

        return ctx


class FavoritesListView(TemplateView):
    template_name = "catalog/favorites.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_authenticated:
            favs = (
                Favorite.objects.filter(user=user)
                .select_related("product")
                .order_by("-created_at")
            )
            products = [
                f.product
                for f in favs
                if f.product.is_active
                and not f.product.is_archived
            ]
        else:
            ids = _get_session_favorites(self.request)
            order = {pid: i for i, pid in enumerate(reversed(ids))}
            qs = Product.objects.filter(
                pk__in=ids,
                is_active=True,
                is_archived=False,
            )
            products = sorted(qs, key=lambda p: order.get(p.pk, 0))

        ctx["products"] = products
        return ctx


class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_url = reverse_lazy("dashboard:products_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        # catalog-ul NU mai creează produse de tip auction
        form.instance.sale_type = "FIXED"
        form.instance.auction_start_price = None
        form.instance.auction_buy_now_price = None
        form.instance.auction_reserve_price = None
        form.instance.auction_end_at = None

        # pentru moment: aprobăm automat produsele create din acest formular
        form.instance.moderation_status = "APPROVED"
        response = super().form_valid(form)

        extra_images = form.cleaned_data.get("extra_images") or []
        for idx, img in enumerate(extra_images):
            ProductImage.objects.create(
                product=self.object,
                image=img,
                position=idx,
            )
        return response


class ProductUpdateView(UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "catalog/product_form.html"
    success_url = reverse_lazy("dashboard:products_list")

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def form_valid(self, form):
        # la editare din catalog forțăm în continuare FIXED și curățăm câmpurile de auction
        form.instance.sale_type = "FIXED"
        form.instance.auction_start_price = None
        form.instance.auction_buy_now_price = None
        form.instance.auction_reserve_price = None
        form.instance.auction_end_at = None

        response = super().form_valid(form)

        existing_count = self.object.images.count()
        extra_images = form.cleaned_data.get("extra_images") or []
        for idx, img in enumerate(extra_images, start=existing_count):
            ProductImage.objects.create(
                product=self.object,
                image=img,
                position=idx,
            )
        return response


class ProductDeleteView(DeleteView):
    model = Product
    template_name = "catalog/product_confirm_delete.html"
    success_url = reverse_lazy("dashboard:products_list")

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)
