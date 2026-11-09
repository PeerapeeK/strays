from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import (
    DogForm,
    DogHealthRecordForm,
    InterviewBookingForm,
    InterviewRejectForm,
    InterviewResultForm,
    RegistrationForm,
    StaffCreateForm,
    UserEditForm,
)
from .models import (
    Assessment,
    Dog,
    HousingPhoto,
    InterviewPhoto,
    InterviewRequest,
    InterviewResult,
    notify,
)
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


@role_required(ADOPTER)
def interview_book(request, dog_id):
    dog = get_object_or_404(Dog, pk=dog_id)
    if dog.status != Dog.AVAILABLE:
        messages.error(request, 'สุนัขตัวนี้ไม่พร้อมรับการจองคิวสัมภาษณ์')
        return redirect('public_dog_detail', pk=dog.pk)

    profile = request.user.profile
    require_pdpa = profile.pdpa_consent_at is None
    initial = {
        'full_name': profile.full_name,
        'phone': profile.phone,
        'address': profile.address,
    }

    if request.method == 'POST':
        form = InterviewBookingForm(
            request.POST, request.FILES, require_pdpa=require_pdpa
        )
        if form.is_valid():
            interview = None
            with transaction.atomic():
                scheduled_at = form.cleaned_data['scheduled_at']
                slot_taken = InterviewRequest.objects.select_for_update().filter(
                    scheduled_at=scheduled_at,
                    status__in=InterviewRequest.ACTIVE_STATUSES,
                ).exists()
                if slot_taken:
                    form.add_error(
                        'scheduled_at',
                        'ช่วงเวลานี้มีผู้จองแล้ว กรุณาเลือกเวลาอื่น',
                    )
                else:
                    interview = InterviewRequest.objects.create(
                        adopter=request.user,
                        dog=dog,
                        scheduled_at=scheduled_at,
                        full_name=form.cleaned_data['full_name'],
                        phone=form.cleaned_data['phone'],
                        address=form.cleaned_data['address'],
                    )
                    Assessment.objects.create(
                        interview_request=interview,
                        housing_type=form.cleaned_data['housing_type'],
                        has_other_pets=form.cleaned_data['has_other_pets'],
                        household_members=form.cleaned_data['household_members'],
                        experience=form.cleaned_data['experience'],
                        motivation=form.cleaned_data['motivation'],
                        agree_home_visit=form.cleaned_data['agree_home_visit'],
                    )
                    for image in form.cleaned_data['housing_photos']:
                        HousingPhoto.objects.create(
                            interview_request=interview, image=image
                        )

                    profile.full_name = form.cleaned_data['full_name']
                    profile.phone = form.cleaned_data['phone']
                    profile.address = form.cleaned_data['address']
                    if require_pdpa:
                        profile.pdpa_consent_at = timezone.now()
                    profile.save()

                    notify(
                        request.user,
                        'จองคิวสัมภาษณ์สำเร็จ',
                        f'รหัสการนัดหมายของคุณคือ {interview.code} '
                        f'สำหรับสุนัข {dog.name} ในวันที่ '
                        f'{timezone.localtime(interview.scheduled_at):%d/%m/%Y %H:%M}',
                        dedupe_key=f'interview-booked-{interview.pk}',
                    )
            if interview:
                messages.success(
                    request,
                    f'จองคิวสัมภาษณ์สำเร็จ รหัสการนัดหมายของคุณคือ {interview.code}',
                )
                return redirect('interview_detail', pk=interview.pk)
    else:
        form = InterviewBookingForm(initial=initial, require_pdpa=require_pdpa)

    context = {'form': form, 'dog': dog, 'require_pdpa': require_pdpa}
    return render(request, 'interviews/book.html', context)


@role_required(ADOPTER)
def interview_list(request):
    interviews = InterviewRequest.objects.filter(
        adopter=request.user
    ).select_related('dog')
    return render(request, 'interviews/list.html', {'interviews': interviews})


@role_required(ADOPTER)
def interview_detail(request, pk):
    interview = get_object_or_404(
        InterviewRequest.objects.select_related('dog'), pk=pk, adopter=request.user
    )
    return render(request, 'interviews/detail.html', {'interview': interview})


@role_required(ADOPTER)
@require_POST
def interview_cancel(request, pk):
    interview = get_object_or_404(
        InterviewRequest, pk=pk, adopter=request.user
    )
    if interview.status not in InterviewRequest.ACTIVE_STATUSES:
        messages.error(request, 'ไม่สามารถยกเลิกนัดหมายนี้ได้')
    elif interview.scheduled_at - timezone.now() < timedelta(hours=24):
        messages.error(
            request,
            'สามารถยกเลิกนัดหมายได้ล่วงหน้าอย่างน้อย 24 ชั่วโมงเท่านั้น',
        )
    else:
        interview.status = InterviewRequest.CANCELLED
        interview.save(update_fields=['status', 'updated_at'])
        notify(
            request.user,
            'ยกเลิกนัดหมายสัมภาษณ์แล้ว',
            f'นัดหมายรหัส {interview.code} ถูกยกเลิกแล้ว',
            dedupe_key=f'interview-cancelled-{interview.pk}',
        )
        messages.success(request, 'ยกเลิกนัดหมายสัมภาษณ์สำเร็จ')
    return redirect('interview_detail', pk=interview.pk)


@role_required(ADOPTER)
@require_POST
def interview_confirm_attendance(request, pk):
    interview = get_object_or_404(
        InterviewRequest, pk=pk, adopter=request.user
    )
    if interview.status != InterviewRequest.CONFIRMED:
        messages.error(
            request, 'สามารถยืนยันการเข้าร่วมได้เฉพาะนัดหมายที่ได้รับการยืนยันแล้ว'
        )
    elif interview.attendance_confirmed_at is not None:
        messages.info(request, 'คุณได้ยืนยันการเข้าร่วมนัดหมายนี้แล้ว')
    else:
        interview.attendance_confirmed_at = timezone.now()
        interview.save(update_fields=['attendance_confirmed_at', 'updated_at'])
        messages.success(request, 'ยืนยันการเข้าร่วมสัมภาษณ์สำเร็จ')
    return redirect('interview_detail', pk=interview.pk)


@role_required(STAFF, ADMIN)
def staff_interview_list(request):
    interviews = InterviewRequest.objects.select_related('dog', 'adopter')

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    date = request.GET.get('date', '')

    if q:
        interviews = interviews.filter(
            Q(code__icontains=q)
            | Q(dog__name__icontains=q)
            | Q(full_name__icontains=q)
            | Q(adopter__username__icontains=q)
        )
    if status in dict(InterviewRequest.STATUS_CHOICES):
        interviews = interviews.filter(status=status)
    parsed_date = parse_date(date) if date else None
    if parsed_date:
        interviews = interviews.filter(scheduled_at__date=parsed_date)

    context = {
        'interviews': interviews,
        'q': q,
        'status': status,
        'date': date,
        'status_choices': InterviewRequest.STATUS_CHOICES,
        'reject_form': InterviewRejectForm(auto_id=False),
    }
    return render(request, 'interviews/staff_list.html', context)


@role_required(STAFF, ADMIN)
@require_POST
def staff_interview_confirm(request, pk):
    interview = get_object_or_404(InterviewRequest, pk=pk)
    if interview.status != InterviewRequest.PENDING:
        messages.error(request, 'ยืนยันได้เฉพาะนัดหมายที่รอการยืนยันเท่านั้น')
    else:
        interview.status = InterviewRequest.CONFIRMED
        interview.save(update_fields=['status', 'updated_at'])
        notify(
            interview.adopter,
            'นัดหมายสัมภาษณ์ได้รับการยืนยันแล้ว',
            f'นัดหมายรหัส {interview.code} สำหรับสุนัข {interview.dog.name} '
            f'ในวันที่ {timezone.localtime(interview.scheduled_at):%d/%m/%Y %H:%M} '
            'ได้รับการยืนยันแล้ว',
            dedupe_key=f'interview-confirmed-{interview.pk}',
        )
        messages.success(request, f'ยืนยันนัดหมาย {interview.code} สำเร็จ')
    return redirect('staff_interview_list')


@role_required(STAFF, ADMIN)
@require_POST
def staff_interview_reject(request, pk):
    interview = get_object_or_404(InterviewRequest, pk=pk)
    form = InterviewRejectForm(request.POST)
    if interview.status != InterviewRequest.PENDING:
        messages.error(request, 'ปฏิเสธได้เฉพาะนัดหมายที่รอการยืนยันเท่านั้น')
    elif form.is_valid():
        interview.status = InterviewRequest.REJECTED
        interview.reject_reason = form.cleaned_data['reason']
        interview.save(update_fields=['status', 'reject_reason', 'updated_at'])
        notify(
            interview.adopter,
            'นัดหมายสัมภาษณ์ถูกปฏิเสธ',
            f'นัดหมายรหัส {interview.code} ถูกปฏิเสธ '
            f'เนื่องจาก {interview.reject_reason}',
            dedupe_key=f'interview-rejected-{interview.pk}',
        )
        messages.success(request, f'ปฏิเสธนัดหมาย {interview.code} สำเร็จ')
    else:
        messages.error(request, 'กรุณาระบุเหตุผลการปฏิเสธ')
    return redirect('staff_interview_list')


@role_required(STAFF, ADMIN)
def staff_interview_result(request, pk):
    interview = get_object_or_404(
        InterviewRequest.objects.select_related('dog', 'adopter'), pk=pk
    )
    if InterviewResult.objects.filter(interview_request=interview).exists():
        messages.info(request, 'นัดหมายนี้มีผลการสัมภาษณ์แล้ว')
        return redirect('staff_interview_list')
    if interview.status != InterviewRequest.CONFIRMED:
        messages.error(request, 'บันทึกผลได้เฉพาะนัดหมายที่ยืนยันแล้วเท่านั้น')
        return redirect('staff_interview_list')

    if request.method == 'POST':
        form = InterviewResultForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                result = InterviewResult.objects.create(
                    interview_request=interview,
                    outcome=form.cleaned_data['outcome'],
                    notes=form.cleaned_data['notes'],
                    recorded_by=request.user,
                )
                for image in form.cleaned_data['photos']:
                    InterviewPhoto.objects.create(result=result, image=image)

                interview.status = InterviewRequest.COMPLETED
                interview.save(update_fields=['status', 'updated_at'])

                notify(
                    interview.adopter,
                    'ผลการสัมภาษณ์',
                    f'ผลการสัมภาษณ์รหัส {interview.code} คือ '
                    f'{result.get_outcome_display()}',
                    dedupe_key=f'interview-result-{interview.pk}',
                )
            messages.success(request, f'บันทึกผลการสัมภาษณ์ {interview.code} สำเร็จ')
            return redirect('staff_interview_list')
    else:
        form = InterviewResultForm()

    return render(
        request,
        'interviews/result_form.html',
        {'form': form, 'interview': interview},
    )


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
