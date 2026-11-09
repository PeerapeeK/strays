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
    ContractForm,
    DogForm,
    DogHealthRecordForm,
    FollowUpEvaluationForm,
    FollowUpSubmitForm,
    HomeVisitForm,
    HomeVisitRescheduleForm,
    InterviewBookingForm,
    InterviewRejectForm,
    InterviewResultForm,
    RegistrationForm,
    StaffCreateForm,
    UserEditForm,
)
from .models import (
    AdoptionContract,
    Assessment,
    Dog,
    FollowUp,
    FollowUpEvaluation,
    FollowUpEvaluationPhoto,
    FollowUpPhoto,
    HomeVisit,
    HousingPhoto,
    InterviewPhoto,
    InterviewRequest,
    InterviewResult,
    notify,
)
from .permissions import ADOPTER, ADMIN, STAFF, role_required, user_role
from .services import activate_contract, create_follow_ups, notify_staff


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

@role_required(STAFF, ADMIN)
def staff_contract_list(request):
    contracts = AdoptionContract.objects.select_related(
        'interview_request__dog', 'interview_request__adopter'
    )

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    if q:
        contracts = contracts.filter(
            Q(contract_no__icontains=q)
            | Q(interview_request__dog__name__icontains=q)
            | Q(interview_request__adopter__username__icontains=q)
            | Q(interview_request__full_name__icontains=q)
        )
    if status in dict(AdoptionContract.STATUS_CHOICES):
        contracts = contracts.filter(status=status)

    context = {
        'contracts': contracts,
        'q': q,
        'status': status,
        'status_choices': AdoptionContract.STATUS_CHOICES,
    }
    return render(request, 'contracts/staff_list.html', context)


@role_required(STAFF, ADMIN)
def staff_contract_create(request, interview_pk):
    interview = get_object_or_404(
        InterviewRequest.objects.select_related('dog', 'adopter'),
        pk=interview_pk,
    )

    if not interview.is_approved:
        messages.error(
            request, 'สร้างสัญญาได้เฉพาะการสัมภาษณ์ที่ผ่านการอนุมัติแล้วเท่านั้น'
        )
        return redirect('staff_interview_list')

    existing = getattr(interview, 'contract', None)
    if existing is not None:
        messages.info(request, 'การสัมภาษณ์นี้มีสัญญาแล้ว')
        return redirect('staff_contract_detail', pk=existing.pk)

    if request.method == 'POST':
        form = ContractForm(request.POST)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.interview_request = interview
            contract.status = AdoptionContract.DRAFT
            contract.save()

            notify(
                interview.adopter,
                'สร้างสัญญารับอุปการะแล้ว',
                f'สัญญาเลขที่ {contract.contract_no} สำหรับสุนัข '
                f'{interview.dog.name} ถูกสร้างแล้ว',
                dedupe_key=f'contract-created-{contract.pk}',
            )

            if request.POST.get('action') == 'activate':
                activate_contract(contract)
                messages.success(
                    request,
                    f'สร้างและเปิดใช้งานสัญญา {contract.contract_no} สำเร็จ',
                )
            else:
                messages.success(
                    request, f'บันทึกสัญญา {contract.contract_no} เป็นฉบับร่างสำเร็จ'
                )
            return redirect('staff_contract_detail', pk=contract.pk)
    else:
        form = ContractForm()

    context = {'form': form, 'interview': interview}
    return render(request, 'contracts/form.html', context)


@role_required(STAFF, ADMIN)
def staff_contract_detail(request, pk):
    contract = get_object_or_404(
        AdoptionContract.objects.select_related(
            'interview_request__dog', 'interview_request__adopter'
        ),
        pk=pk,
    )
    context = {
        'contract': contract,
        'follow_ups': contract.follow_ups.all(),
        'home_visits': contract.home_visits.all(),
        'home_visit_form': HomeVisitForm(),
    }
    return render(request, 'contracts/staff_detail.html', context)


@role_required(STAFF, ADMIN)
def staff_contract_edit(request, pk):
    contract = get_object_or_404(AdoptionContract, pk=pk)
    if request.method == 'POST':
        form = ContractForm(request.POST, instance=contract)
        if form.is_valid():
            contract = form.save()
            notify(
                contract.adopter,
                'สัญญารับอุปการะถูกแก้ไข',
                f'สัญญาเลขที่ {contract.contract_no} ถูกแก้ไขโดยเจ้าหน้าที่',
                dedupe_key=f'contract-updated-{contract.pk}-'
                f'{int(timezone.now().timestamp())}',
            )
            messages.success(request, 'บันทึกสัญญาสำเร็จ')
            return redirect('staff_contract_detail', pk=contract.pk)
    else:
        form = ContractForm(instance=contract)
    return render(request, 'contracts/form.html', {'form': form, 'contract': contract})


@role_required(STAFF, ADMIN)
@require_POST
def staff_contract_activate(request, pk):
    contract = get_object_or_404(
        AdoptionContract.objects.select_related('interview_request__dog'), pk=pk
    )
    if contract.status == AdoptionContract.ACTIVE:
        messages.info(request, 'สัญญานี้เปิดใช้งานอยู่แล้ว')
    else:
        activate_contract(contract)
        messages.success(request, f'เปิดใช้งานสัญญา {contract.contract_no} สำเร็จ')
    return redirect('staff_contract_detail', pk=contract.pk)


@role_required(ADOPTER)
def contract_list(request):
    contracts = AdoptionContract.objects.filter(
        interview_request__adopter=request.user
    ).select_related('interview_request__dog')
    return render(request, 'contracts/list.html', {'contracts': contracts})


@role_required(ADOPTER)
def contract_detail(request, pk):
    contract = get_object_or_404(
        AdoptionContract.objects.select_related(
            'interview_request__dog', 'interview_request__adopter'
        ),
        pk=pk,
        interview_request__adopter=request.user,
    )
    context = {
        'contract': contract,
        'home_visits': contract.home_visits.all(),
        'reschedule_form': HomeVisitRescheduleForm(),
    }
    return render(request, 'contracts/detail.html', context)


@role_required(ADOPTER)
@require_POST
def contract_acknowledge(request, pk):
    contract = get_object_or_404(
        AdoptionContract, pk=pk, interview_request__adopter=request.user
    )
    if contract.status != AdoptionContract.ACTIVE:
        messages.error(request, 'สามารถยอมรับได้เฉพาะสัญญาที่มีผลบังคับใช้แล้ว')
    elif contract.acknowledged_at is not None:
        messages.info(request, 'คุณได้ยอมรับสัญญานี้แล้ว')
    else:
        contract.acknowledged_at = timezone.now()
        contract.save(update_fields=['acknowledged_at', 'updated_at'])
        notify_staff(
            'ผู้รับอุปการะยอมรับสัญญาแล้ว',
            f'สัญญาเลขที่ {contract.contract_no} ถูกยอมรับโดย '
            f'{contract.interview_request.full_name}',
            dedupe_key=f'contract-acknowledged-{contract.pk}',
        )
        messages.success(request, 'ยอมรับสัญญารับอุปการะสำเร็จ')
    return redirect('contract_detail', pk=contract.pk)


@role_required(ADOPTER)
def followup_list(request):
    follow_ups = FollowUp.objects.filter(
        contract__interview_request__adopter=request.user
    ).select_related('contract__interview_request__dog')
    return render(request, 'follow_ups/list.html', {'follow_ups': follow_ups})


@role_required(ADOPTER)
def followup_detail(request, pk):
    follow_up = get_object_or_404(
        FollowUp.objects.select_related(
            'contract__interview_request__dog', 'contract__interview_request__adopter'
        ),
        pk=pk,
        contract__interview_request__adopter=request.user,
    )
    return render(
        request,
        'follow_ups/detail.html',
        {'follow_up': follow_up, 'form': FollowUpSubmitForm()},
    )


@role_required(ADOPTER)
@require_POST
def followup_submit(request, pk):
    follow_up = get_object_or_404(
        FollowUp.objects.select_related(
            'contract__interview_request__adopter'
        ),
        pk=pk,
        contract__interview_request__adopter=request.user,
    )

    if follow_up.contract.status != AdoptionContract.ACTIVE:
        messages.error(request, 'สัญญายังไม่มีผลบังคับใช้')
        return redirect('followup_detail', pk=follow_up.pk)
    if follow_up.status == FollowUp.SUBMITTED:
        messages.error(request, 'คุณได้ส่งข้อมูลการติดตามผลนี้แล้ว')
        return redirect('followup_detail', pk=follow_up.pk)

    form = FollowUpSubmitForm(request.POST, request.FILES)
    if form.is_valid():
        with transaction.atomic():
            for image in form.cleaned_data['photos']:
                FollowUpPhoto.objects.create(follow_up=follow_up, image=image)
            follow_up.notes = form.cleaned_data.get('notes', '')
            follow_up.status = FollowUp.SUBMITTED
            follow_up.submitted_at = timezone.now()
            follow_up.save(
                update_fields=['notes', 'status', 'submitted_at']
            )

            notify_staff(
                'มีการส่งข้อมูลติดตามผล',
                f'การติดตามผล {follow_up.day_offset} วัน ของสัญญา '
                f'{follow_up.contract.contract_no} ถูกส่งแล้ว',
                dedupe_key=f'followup-submitted-{follow_up.pk}',
            )
        messages.success(request, 'ส่งข้อมูลการติดตามผลสำเร็จ')
        return redirect('followup_detail', pk=follow_up.pk)

    return render(
        request,
        'follow_ups/detail.html',
        {'follow_up': follow_up, 'form': form},
    )


@role_required(STAFF, ADMIN)
def staff_followup_list(request):
    follow_ups = FollowUp.objects.select_related(
        'contract__interview_request__dog', 'contract__interview_request__adopter'
    )
    status = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    if status in dict(FollowUp.STATUS_CHOICES):
        follow_ups = follow_ups.filter(status=status)
    if q:
        follow_ups = follow_ups.filter(
            Q(contract__contract_no__icontains=q)
            | Q(contract__interview_request__dog__name__icontains=q)
            | Q(contract__interview_request__full_name__icontains=q)
        )

    context = {
        'follow_ups': follow_ups,
        'status': status,
        'q': q,
        'status_choices': FollowUp.STATUS_CHOICES,
    }
    return render(request, 'follow_ups/staff_list.html', context)


@role_required(STAFF, ADMIN)
def staff_followup_detail(request, pk):
    follow_up = get_object_or_404(
        FollowUp.objects.select_related(
            'contract__interview_request__dog', 'contract__interview_request__adopter'
        ),
        pk=pk,
    )
    return render(
        request,
        'follow_ups/staff_detail.html',
        {'follow_up': follow_up, 'form': FollowUpEvaluationForm()},
    )


@role_required(STAFF, ADMIN)
def staff_followup_evaluate(request, pk):
    follow_up = get_object_or_404(
        FollowUp.objects.select_related(
            'contract__interview_request__dog', 'contract__interview_request__adopter'
        ),
        pk=pk,
    )
    if follow_up.status != FollowUp.SUBMITTED:
        messages.error(request, 'บันทึกผลประเมินได้เฉพาะการติดตามผลที่ส่งข้อมูลแล้ว')
        return redirect('staff_followup_detail', pk=follow_up.pk)
    if getattr(follow_up, 'evaluation', None) is not None:
        messages.info(request, 'การติดตามผลนี้มีผลประเมินแล้ว')
        return redirect('staff_followup_detail', pk=follow_up.pk)

    if request.method == 'POST':
        form = FollowUpEvaluationForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                evaluation = FollowUpEvaluation.objects.create(
                    follow_up=follow_up,
                    evaluator=request.user,
                    housing_condition=form.cleaned_data['housing_condition'],
                    dog_condition=form.cleaned_data['dog_condition'],
                    notes=form.cleaned_data.get('notes', ''),
                )
                for image in form.cleaned_data['photos']:
                    FollowUpEvaluationPhoto.objects.create(
                        evaluation=evaluation, image=image
                    )

                notify(
                    follow_up.contract.adopter,
                    'ผลประเมินการติดตามผล',
                    f'การติดตามผล {follow_up.day_offset} วัน ของสัญญา '
                    f'{follow_up.contract.contract_no} ได้รับการประเมินแล้ว',
                    dedupe_key=f'followup-evaluated-{follow_up.pk}',
                )
            messages.success(request, 'บันทึกผลประเมินการติดตามผลสำเร็จ')
            return redirect('staff_followup_detail', pk=follow_up.pk)
    else:
        form = FollowUpEvaluationForm()

    return render(
        request,
        'follow_ups/staff_detail.html',
        {'follow_up': follow_up, 'form': form},
    )


@role_required(STAFF, ADMIN)
def homevisit_create(request, contract_pk):
    contract = get_object_or_404(AdoptionContract, pk=contract_pk)
    if contract.status != AdoptionContract.ACTIVE:
        messages.error(request, 'สร้างนัดตรวจบ้านได้เฉพาะสัญญาที่มีผลบังคับใช้แล้ว')
        return redirect('staff_contract_detail', pk=contract.pk)

    if request.method == 'POST':
        form = HomeVisitForm(request.POST)
        if form.is_valid():
            home_visit = form.save(commit=False)
            home_visit.contract = contract
            home_visit.created_by = request.user
            home_visit.status = HomeVisit.SCHEDULED
            home_visit.save()
            notify(
                contract.adopter,
                'นัดตรวจบ้านใหม่',
                f'สัญญาเลขที่ {contract.contract_no} มีนัดตรวจบ้านวันที่ '
                f'{timezone.localtime(home_visit.scheduled_at):%d/%m/%Y %H:%M}',
                dedupe_key=f'homevisit-created-{home_visit.pk}',
            )
            messages.success(request, 'สร้างนัดตรวจบ้านสำเร็จ')
            return redirect('staff_contract_detail', pk=contract.pk)
    else:
        form = HomeVisitForm()

    return render(
        request,
        'home_visits/form.html',
        {'form': form, 'contract': contract, 'is_edit': False},
    )


@role_required(STAFF, ADMIN)
def homevisit_edit(request, pk):
    home_visit = get_object_or_404(
        HomeVisit.objects.select_related('contract'), pk=pk
    )
    if request.method == 'POST':
        form = HomeVisitForm(request.POST, instance=home_visit)
        if form.is_valid():
            home_visit = form.save(commit=False)
            home_visit.status = HomeVisit.SCHEDULED
            home_visit.save()
            notify(
                home_visit.contract.adopter,
                'แก้ไขนัดตรวจบ้าน',
                f'นัดตรวจบ้านของสัญญา {home_visit.contract.contract_no} '
                f'ถูกแก้ไขเป็นวันที่ '
                f'{timezone.localtime(home_visit.scheduled_at):%d/%m/%Y %H:%M}',
                dedupe_key=f'homevisit-updated-{home_visit.pk}-'
                f'{int(timezone.now().timestamp())}',
            )
            messages.success(request, 'แก้ไขนัดตรวจบ้านสำเร็จ')
            return redirect(
                'staff_contract_detail', pk=home_visit.contract.pk
            )
    else:
        form = HomeVisitForm(instance=home_visit)
    return render(
        request,
        'home_visits/form.html',
        {
            'form': form,
            'contract': home_visit.contract,
            'home_visit': home_visit,
            'is_edit': True,
        },
    )


@role_required(ADOPTER)
@require_POST
def homevisit_request_reschedule(request, pk):
    home_visit = get_object_or_404(
        HomeVisit.objects.select_related('contract'),
        pk=pk,
        contract__interview_request__adopter=request.user,
    )
    form = HomeVisitRescheduleForm(request.POST)

    if home_visit.status == HomeVisit.RESCHEDULE_REQUESTED:
        messages.error(request, 'คุณได้ขอเลื่อนนัดนี้แล้ว')
    elif form.is_valid():
        home_visit.requested_scheduled_at = form.cleaned_data[
            'requested_scheduled_at'
        ]
        home_visit.reschedule_reason = form.cleaned_data['reason']
        home_visit.reschedule_requested_at = timezone.now()
        home_visit.status = HomeVisit.RESCHEDULE_REQUESTED
        home_visit.save()
        notify_staff(
            'คำขอเลื่อนนัดตรวจบ้าน',
            f'สัญญาเลขที่ {home_visit.contract.contract_no} มีคำขอเลื่อนนัด'
            f'ตรวจบ้านเป็นวันที่ '
            f'{timezone.localtime(home_visit.requested_scheduled_at):%d/%m/%Y %H:%M}',
            dedupe_key=f'homevisit-reschedule-requested-{home_visit.pk}-'
            f'{int(timezone.now().timestamp())}',
        )
        messages.success(request, 'ส่งคำขอเลื่อนนัดตรวจบ้านสำเร็จ')
    else:
        messages.error(request, 'กรุณากรอกข้อมูลการขอเลื่อนนัดให้ถูกต้อง')
    return redirect('contract_detail', pk=home_visit.contract.pk)


@role_required(STAFF, ADMIN)
@require_POST
def homevisit_approve(request, pk):
    home_visit = get_object_or_404(
        HomeVisit.objects.select_related('contract'), pk=pk
    )
    if home_visit.status != HomeVisit.RESCHEDULE_REQUESTED:
        messages.error(request, 'อนุมัติได้เฉพาะนัดที่มีคำขอเลื่อนนัดเท่านั้น')
    elif home_visit.requested_scheduled_at is None:
        messages.error(request, 'ไม่พบวันและเวลาที่ขอเลื่อน')
    else:
        home_visit.scheduled_at = home_visit.requested_scheduled_at
        home_visit.status = HomeVisit.APPROVED
        home_visit.save()
        notify(
            home_visit.contract.adopter,
            'อนุมัติการเลื่อนนัดตรวจบ้าน',
            f'คำขอเลื่อนนัดตรวจบ้านของสัญญา '
            f'{home_visit.contract.contract_no} ได้รับการอนุมัติแล้ว '
            f'เป็นวันที่ '
            f'{timezone.localtime(home_visit.scheduled_at):%d/%m/%Y %H:%M}',
            dedupe_key=f'homevisit-reschedule-approved-{home_visit.pk}-'
            f'{int(timezone.now().timestamp())}',
        )
        messages.success(request, 'อนุมัติการเลื่อนนัดตรวจบ้านสำเร็จ')
    return redirect('staff_contract_detail', pk=home_visit.contract.pk)


@role_required(STAFF, ADMIN)
@require_POST
def homevisit_deny(request, pk):
    home_visit = get_object_or_404(
        HomeVisit.objects.select_related('contract'), pk=pk
    )
    if home_visit.status != HomeVisit.RESCHEDULE_REQUESTED:
        messages.error(request, 'ปฏิเสธได้เฉพาะนัดที่มีคำขอเลื่อนนัดเท่านั้น')
    else:
        home_visit.status = HomeVisit.DENIED
        home_visit.save()
        notify(
            home_visit.contract.adopter,
            'ปฏิเสธการเลื่อนนัดตรวจบ้าน',
            f'คำขอเลื่อนนัดตรวจบ้านของสัญญา '
            f'{home_visit.contract.contract_no} ถูกปฏิเสธ',
            dedupe_key=f'homevisit-reschedule-denied-{home_visit.pk}-'
            f'{int(timezone.now().timestamp())}',
        )
        messages.success(request, 'ปฏิเสธการเลื่อนนัดตรวจบ้านสำเร็จ')
    return redirect('staff_contract_detail', pk=home_visit.contract.pk)
