from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import User, BillType, Bill, PaymentRecord, PaymentMethod


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        User.objects.create_user(username=username, password=password)
        return redirect('login')
    return render(request, 'register.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('bill_list')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'login.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('login')

@login_required
def bill_list(request):
    bills = Bill.objects.filter(user=request.user, is_paid=False)
    return render(request, 'bill_list.html', {'bills': bills})

@login_required
def pay_bill(request, bill_id):
    bill = Bill.objects.get(id=bill_id)
    if request.method == 'POST':
        bill.is_paid = True
        bill.save()
        PaymentRecord.objects.create(user=request.user, bill=bill, payment_amount=bill.amount)
        messages.success(request, 'Payment successful')
        return redirect('bill_list')
    return render(request, 'pay_bill.html', {'bill': bill})

@login_required
def payment_record_list(request):
    records = PaymentRecord.objects.filter(user=request.user)
    return render(request, 'payment_record_list.html', {'records': records})


@login_required
def user_profile(request):
    if request.method == 'POST':
        # Update user info
        request.user.phone_number = request.POST.get('phone_number', request.user.phone_number)
        # You can add more fields here if needed
        request.user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('user_profile')
    return render(request, 'user_profile.html')

@staff_member_required
def bill_type_list(request):
    bill_types = BillType.objects.all()
    return render(request, 'bill_type_list.html', {'bill_types': bill_types})


@staff_member_required
def bill_type_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            BillType.objects.create(name=name)
            messages.success(request, f'Bill Type "{name}" created successfully.')
        return redirect('bill_type_list')
    return render(request, 'bill_type_create.html')

@staff_member_required
def bill_type_edit(request, bill_type_id):
    bill_type = get_object_or_404(BillType, id=bill_type_id)
    if request.method == 'POST':
        new_name = request.POST.get('name')
        bill_type.name = new_name
        bill_type.save()
        messages.success(request, f'Bill Type updated to "{new_name}".')
        return redirect('bill_type_list')
    return render(request, 'bill_type_edit.html', {'bill_type': bill_type})

@staff_member_required
def bill_type_delete(request, bill_type_id):
    bill_type = get_object_or_404(BillType, id=bill_type_id)
    bill_type.delete()
    messages.success(request, f'Bill Type "{bill_type.name}" has been deleted.')
    return redirect('bill_type_list')


@login_required
def pay_bill(request, bill_id):
    bill = Bill.objects.get(id=bill_id)
    payment_methods = PaymentMethod.objects.all()
    if request.method == 'POST':
        selected_method_id = request.POST.get('payment_method')
        selected_method = None
        if selected_method_id:
            selected_method = PaymentMethod.objects.get(id=selected_method_id)

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
