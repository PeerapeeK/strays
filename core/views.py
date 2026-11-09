from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    DogForm,
    DogHealthRecordForm,
    RegistrationForm,
    StaffCreateForm,
    UserEditForm,
)
from .models import Dog
from .permissions import ADOPTER, ADMIN, STAFF, role_required, user_role


def home(request):
    return render(request, 'home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ')
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    role = user_role(request.user)
    if role == ADMIN:
        return redirect('admin_dashboard')
    if role == STAFF:
        return redirect('staff_dashboard')
    if role == ADOPTER:
        return redirect('adopter_dashboard')
    messages.error(request, 'บัญชีของคุณยังไม่ได้รับสิทธิ์การใช้งาน')
    return redirect('home')


@role_required(ADOPTER)
def adopter_dashboard(request):
    return render(request, 'dashboard/adopter.html')


@role_required(STAFF, ADMIN)
def staff_dashboard(request):
    return render(request, 'dashboard/staff.html')


@role_required(ADMIN)
def admin_dashboard(request):
    return render(request, 'dashboard/admin.html')


@role_required(ADMIN)
def user_list(request):
    users = User.objects.select_related('profile').order_by('username')
    rows = [{'user': user, 'role': user_role(user)} for user in users]
    return render(request, 'users/user_list.html', {'rows': rows})


@role_required(ADMIN)
def staff_create(request):
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'สร้างบัญชีเจ้าหน้าที่สำเร็จ')
            return redirect('user_list')
    else:
        form = StaffCreateForm()
    return render(request, 'users/staff_form.html', {'form': form})


@role_required(ADMIN)
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'บันทึกข้อมูลผู้ใช้สำเร็จ')
            return redirect('user_list')
    else:
        form = UserEditForm(instance=user)
    return render(request, 'users/user_form.html', {'form': form, 'edit_user': user})


@role_required(ADMIN)
@require_POST
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, 'ไม่สามารถระงับบัญชีของตนเองได้')
        return redirect('user_list')

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    if user.is_active:
        messages.success(request, f'เปิดใช้งานบัญชี {user.username} แล้ว')
    else:
        messages.success(request, f'ระงับการใช้งานบัญชี {user.username} แล้ว')
    return redirect('user_list')


def public_dog_list(request):
    dogs = Dog.objects.filter(status=Dog.AVAILABLE)

    q = request.GET.get('q', '').strip()
    sex = request.GET.get('sex', '')
    size = request.GET.get('size', '')

    if q:
        dogs = dogs.filter(
            Q(name__icontains=q)
            | Q(breed__icontains=q)
            | Q(color__icontains=q)
            | Q(description__icontains=q)
        )
    if sex in dict(Dog.SEX_CHOICES):
        dogs = dogs.filter(sex=sex)
    if size in dict(Dog.SIZE_CHOICES):
        dogs = dogs.filter(size=size)

    context = {
        'dogs': dogs,
        'q': q,
        'sex': sex,
        'size': size,
        'sex_choices': Dog.SEX_CHOICES,
        'size_choices': Dog.SIZE_CHOICES,
    }
    return render(request, 'dogs/public_list.html', context)


def public_dog_detail(request, pk):
    dog = get_object_or_404(Dog, pk=pk)
    return render(request, 'dogs/public_detail.html', {'dog': dog})


@login_required
def interview_book(request, dog_id):
    dog = get_object_or_404(Dog, pk=dog_id)
    return render(request, 'interviews/book.html', {'dog': dog})


@role_required(STAFF, ADMIN)
def dog_list(request):
    dogs = Dog.objects.all()

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    if q:
        dogs = dogs.filter(
            Q(name__icontains=q)
            | Q(breed__icontains=q)
            | Q(color__icontains=q)
            | Q(description__icontains=q)
        )
    if status in dict(Dog.STATUS_CHOICES):
        dogs = dogs.filter(status=status)

    context = {
        'dogs': dogs,
        'q': q,
        'status': status,
        'status_choices': Dog.STATUS_CHOICES,
    }
    return render(request, 'dogs/dog_list.html', context)


@role_required(STAFF, ADMIN)
def dog_create(request):
    if request.method == 'POST':
        form = DogForm(request.POST, request.FILES)
        if form.is_valid():
            dog = form.save()
            messages.success(request, f'เพิ่มข้อมูลสุนัข {dog.name} สำเร็จ')
            return redirect('dog_detail', pk=dog.pk)
    else:
        form = DogForm()
    return render(request, 'dogs/dog_form.html', {'form': form, 'is_edit': False})


@role_required(STAFF, ADMIN)
def dog_detail(request, pk):
    dog = get_object_or_404(Dog, pk=pk)
    if request.method == 'POST':
        form = DogHealthRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.dog = dog
            record.save()
            messages.success(request, 'เพิ่มบันทึกสุขภาพสำเร็จ')
            return redirect('dog_detail', pk=dog.pk)
    else:
        form = DogHealthRecordForm()
    context = {
        'dog': dog,
        'health_records': dog.health_records.all(),
        'form': form,
    }
    return render(request, 'dogs/dog_detail.html', context)


@role_required(STAFF, ADMIN)
def dog_edit(request, pk):
    dog = get_object_or_404(Dog, pk=pk)
    if request.method == 'POST':
        form = DogForm(request.POST, request.FILES, instance=dog)
        if form.is_valid():
            form.save()
            messages.success(request, f'บันทึกข้อมูลสุนัข {dog.name} สำเร็จ')
            return redirect('dog_detail', pk=dog.pk)
    else:
        form = DogForm(instance=dog)
    return render(request, 'dogs/dog_form.html', {'form': form, 'is_edit': True, 'dog': dog})
