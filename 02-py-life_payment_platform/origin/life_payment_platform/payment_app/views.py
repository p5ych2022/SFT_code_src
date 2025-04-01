from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator   # for pagination

from .models import (
    User, BillType, Bill, PaymentRecord, PaymentMethod
)

def register(request):
    """Handles user registration."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists. Please choose another one.')
            return redirect('register')

        # Basic validation example (e.g., ensure password is not empty)
        if not password:
            messages.error(request, 'Password cannot be empty.')
            return redirect('register')

        # Create user if all validations pass
        User.objects.create_user(username=username, password=password)
        messages.success(request, 'Registration successful. Please log in.')
        return redirect('login')

    return render(request, 'register.html')

def user_login(request):
    """Handles user login."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('bill_list')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'login.html')

@login_required
def user_logout(request):
    """Logs out the current user."""
    logout(request)
    return redirect('login')

@login_required
def bill_list(request):
    """Lists unpaid bills for the currently logged-in user."""
    bills = Bill.objects.filter(user=request.user, is_paid=False)
    return render(request, 'bill_list.html', {'bills': bills})

@login_required
def pay_bill(request, bill_id):
    """
    Pays a specific bill, optionally choosing a payment method.
    Includes basic input validation (e.g., checking selected_method_id).
    """
    bill = get_object_or_404(Bill, id=bill_id)
    payment_methods = PaymentMethod.objects.all()
    if request.method == 'POST':
        selected_method_id = request.POST.get('payment_method')
        selected_method = None
        if selected_method_id:
            selected_method = get_object_or_404(PaymentMethod, id=selected_method_id)

        # Validate amount or bill status here if needed...

        bill.is_paid = True
        bill.save()

        PaymentRecord.objects.create(
            user=request.user,
            bill=bill,
            payment_amount=bill.amount,
            payment_method=selected_method
        )
        messages.success(request, 'Payment successful.')
        return redirect('bill_list')

    return render(request, 'pay_bill.html', {
        'bill': bill,
        'payment_methods': payment_methods,
    })

@login_required
def payment_record_list(request):
    """Displays all payment records for the current user with pagination."""
    records = PaymentRecord.objects.filter(user=request.user).order_by('-payment_date')

    # 10 records per page, for example
    paginator = Paginator(records, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'payment_record_list.html', {'page_obj': page_obj})

@login_required
def user_profile(request):
    """Allows user to view and update personal information."""
    if request.method == 'POST':
        # Simple data validation
        phone = request.POST.get('phone_number', '').strip()
        request.user.phone_number = phone
        request.user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('user_profile')
    return render(request, 'user_profile.html')

@staff_member_required
def bill_type_list(request):
    """Staff-only: lists all existing bill types."""
    bill_types = BillType.objects.all()
    return render(request, 'bill_type_list.html', {'bill_types': bill_types})

@staff_member_required
def bill_type_create(request):
    """Staff-only: creates a new bill type."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Bill Type name cannot be empty.')
            return redirect('bill_type_create')
        BillType.objects.create(name=name)
        messages.success(request, f'Bill Type "{name}" created successfully.')
        return redirect('bill_type_list')
    return render(request, 'bill_type_create.html')

@staff_member_required
def bill_type_edit(request, bill_type_id):
    """Staff-only: edits the name of an existing bill type."""
    bill_type = get_object_or_404(BillType, id=bill_type_id)
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()
        if not new_name:
            messages.error(request, 'Bill Type name cannot be empty.')
            return redirect('bill_type_edit', bill_type_id=bill_type_id)
        bill_type.name = new_name
        bill_type.save()
        messages.success(request, f'Bill Type updated to "{new_name}".')
        return redirect('bill_type_list')
    return render(request, 'bill_type_edit.html', {'bill_type': bill_type})

@staff_member_required
def bill_type_delete(request, bill_type_id):
    """Staff-only: deletes a specified bill type."""
    bill_type = get_object_or_404(BillType, id=bill_type_id)
    name_before_delete = bill_type.name
    bill_type.delete()
    messages.success(request, f'Bill Type "{name_before_delete}" has been deleted.')
    return redirect('bill_type_list')
