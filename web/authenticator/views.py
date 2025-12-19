from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import AuthRequest
from .forms import AuthUploadForm

def authenticate_product_view(request):
    if request.method == 'POST':
        form = AuthUploadForm(request.POST, request.FILES)
        if form.is_valid():
            auth_req = form.save(commit=False)
            if request.user.is_authenticated:
                auth_req.user = request.user
            else:
                auth_req.email = form.cleaned_data['email']
            auth_req.submitted_at = timezone.now()
            auth_req.status = AuthRequest.Status.PENDING
            auth_req.save()
            # save uploaded files somewhere for processing...
            messages.success(request, "Cererea a fost trimisă cu succes!")
            return redirect('authenticator:authenticate_history')
    else:
        form = AuthUploadForm()
    return render(request, 'authenticator/authenticate_product.html', {'form': form})

@login_required
def authenticate_history_view(request):
    history = AuthRequest.objects.filter(user=request.user).order_by('-submitted_at')
    return render(request, 'authenticator/authenticate_history.html', {'history': history})

@login_required
def download_certificate_view(request, pk):
    auth_req = get_object_or_404(
        AuthRequest, pk=pk, user=request.user, status=AuthRequest.Status.SUCCESS
    )
    return redirect(auth_req.certificate_file.url)
