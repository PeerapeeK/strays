from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Assessment,
    AdoptionContract,
    DEFAULT_CONTRACT_TERMS,
    Dog,
    DogHealthRecord,
    HomeVisit,
    InterviewResult,
    ShelterSettings,
)
from .permissions import ADOPTER, STAFF
from .validators import validate_image


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not isinstance(data, (list, tuple)):
            data = [data] if data else []
        if not data:
            if self.required:
                raise ValidationError(
                    self.error_messages['required'], code='required'
                )
            return []
        return [super().clean(item, initial) for item in data]


class BootstrapFormMixin:
    """Apply Bootstrap 5 classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get('class', '')
            if isinstance(widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css = 'form-select'
            elif isinstance(widget, forms.FileInput):
                css = 'form-control'
            else:
                css = 'form-control'
            widget.attrs['class'] = f'{existing} {css}'.strip()
            if widget.__class__.__name__ == 'Textarea':
                widget.attrs.setdefault('rows', 3)


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    full_name = forms.CharField(label='ชื่อ-นามสกุล', max_length=150)
    phone = forms.CharField(label='เบอร์โทรศัพท์', max_length=20)
    address = forms.CharField(label='ที่อยู่', widget=forms.Textarea)
    pdpa_consent = forms.BooleanField(
        label='ข้าพเจ้ายินยอมให้จัดเก็บและใช้ข้อมูลส่วนบุคคลตามพระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล (PDPA)',
        required=True,
        error_messages={'required': 'จำเป็นต้องยินยอมให้เก็บข้อมูลส่วนบุคคลก่อนสมัครสมาชิก'},
    )

    class Meta:
        model = User
        fields = ('username',)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile = user.profile
            profile.full_name = self.cleaned_data['full_name']
            profile.phone = self.cleaned_data['phone']
            profile.address = self.cleaned_data['address']
            profile.pdpa_consent_at = timezone.now()
            profile.save()
            group, _ = Group.objects.get_or_create(name=ADOPTER)
            user.groups.add(group)
        return user


class StaffCreateForm(BootstrapFormMixin, UserCreationForm):
    full_name = forms.CharField(label='ชื่อ-นามสกุล', max_length=150)
    phone = forms.CharField(label='เบอร์โทรศัพท์', max_length=20)
    address = forms.CharField(label='ที่อยู่', widget=forms.Textarea, required=False)

    class Meta:
        model = User
        fields = ('username',)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile = user.profile
            profile.full_name = self.cleaned_data['full_name']
            profile.phone = self.cleaned_data['phone']
            profile.address = self.cleaned_data.get('address', '')
            profile.save()
            group, _ = Group.objects.get_or_create(name=STAFF)
            user.groups.add(group)
        return user


class UserEditForm(BootstrapFormMixin, forms.ModelForm):
    full_name = forms.CharField(label='ชื่อ-นามสกุล', max_length=150, required=False)
    phone = forms.CharField(label='เบอร์โทรศัพท์', max_length=20, required=False)
    address = forms.CharField(label='ที่อยู่', widget=forms.Textarea, required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {
            'first_name': 'ชื่อ',
            'last_name': 'นามสกุล',
            'email': 'อีเมล',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
            if profile:
                self.fields['full_name'].initial = profile.full_name
                self.fields['phone'].initial = profile.phone
                self.fields['address'].initial = profile.address

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = user.profile
            profile.full_name = self.cleaned_data.get('full_name', '')
            profile.phone = self.cleaned_data.get('phone', '')
            profile.address = self.cleaned_data.get('address', '')
            profile.save()
        return user


class DogForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Dog
        fields = (
            'name', 'breed', 'sex', 'age_months', 'size', 'color',
            'description', 'vaccinated', 'sterilized', 'status',
            'photo', 'intake_date',
        )
        widgets = {
            'intake_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class DogHealthRecordForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DogHealthRecord
        fields = ('record_date', 'title', 'description', 'veterinarian')
        widgets = {
            'record_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class InterviewBookingForm(BootstrapFormMixin, forms.Form):
    full_name = forms.CharField(
        label='ชื่อ-นามสกุล',
        max_length=150,
        error_messages={'required': 'กรุณากรอกชื่อ-นามสกุล'},
    )
    phone = forms.CharField(
        label='เบอร์โทรศัพท์',
        max_length=20,
        error_messages={'required': 'กรุณากรอกเบอร์โทรศัพท์'},
    )
    address = forms.CharField(
        label='ที่อยู่',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณากรอกที่อยู่'},
    )
    housing_type = forms.ChoiceField(
        label='ประเภทที่อยู่อาศัย',
        choices=Assessment.HOUSING_CHOICES,
        error_messages={'required': 'กรุณาเลือกประเภทที่อยู่อาศัย'},
    )
    has_other_pets = forms.BooleanField(
        label='มีสัตว์เลี้ยงอื่นอยู่แล้ว', required=False
    )
    household_members = forms.IntegerField(
        label='จำนวนสมาชิกในบ้าน',
        min_value=1,
        initial=1,
        error_messages={
            'required': 'กรุณากรอกจำนวนสมาชิกในบ้าน',
            'min_value': 'จำนวนสมาชิกในบ้านต้องมีอย่างน้อย 1 คน',
            'invalid': 'กรุณากรอกจำนวนสมาชิกในบ้านเป็นตัวเลข',
        },
    )
    experience = forms.CharField(
        label='ประสบการณ์เลี้ยงสุนัข',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณากรอกประสบการณ์เลี้ยงสุนัข'},
    )
    motivation = forms.CharField(
        label='เหตุผลที่ต้องการรับอุปการะ',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณากรอกเหตุผลที่ต้องการรับอุปการะ'},
    )
    agree_home_visit = forms.BooleanField(
        label='ยินยอมให้เจ้าหน้าที่เข้าตรวจบ้าน',
        error_messages={'required': 'จำเป็นต้องยินยอมให้เจ้าหน้าที่เข้าตรวจบ้าน'},
    )
    scheduled_at = forms.DateTimeField(
        label='วันและเวลาสัมภาษณ์',
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'],
        error_messages={
            'required': 'กรุณาเลือกวันและเวลาสัมภาษณ์',
            'invalid': 'รูปแบบวันและเวลาไม่ถูกต้อง',
        },
    )
    housing_photos = MultipleFileField(
        label='รูปถ่ายที่อยู่อาศัย (1-5 รูป)',
        widget=MultipleFileInput(
            attrs={'multiple': True, 'accept': '.jpg,.jpeg,.png,image/*'}
        ),
        error_messages={'required': 'กรุณาอัปโหลดรูปถ่ายที่อยู่อาศัย 1-5 รูป'},
    )
    pdpa_consent = forms.BooleanField(
        label='ข้าพเจ้ายินยอมให้จัดเก็บและใช้ข้อมูลส่วนบุคคลตามพระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล (PDPA)',
        required=False,
        error_messages={'required': 'จำเป็นต้องยินยอมให้เก็บข้อมูลส่วนบุคคลก่อนจองคิวสัมภาษณ์'},
    )

    def __init__(self, *args, require_pdpa=False, **kwargs):
        super().__init__(*args, **kwargs)
        if require_pdpa:
            self.fields['pdpa_consent'].required = True
        else:
            self.fields.pop('pdpa_consent')

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data['scheduled_at']
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(
                scheduled_at, timezone.get_current_timezone()
            )
        if scheduled_at <= timezone.now():
            raise ValidationError('กรุณาเลือกวันและเวลาในอนาคต')

        shelter = ShelterSettings.load()
        local_time = timezone.localtime(scheduled_at).time()
        if not (shelter.opening_time <= local_time < shelter.closing_time):
            raise ValidationError(
                'กรุณาเลือกเวลาในช่วงเปิดทำการ '
                f'{shelter.opening_time:%H:%M}-{shelter.closing_time:%H:%M} น.'
            )
        return scheduled_at

    def clean_housing_photos(self):
        photos = self.cleaned_data.get('housing_photos') or []
        if not 1 <= len(photos) <= 5:
            raise ValidationError('กรุณาอัปโหลดรูปถ่ายที่อยู่อาศัย 1-5 รูป')
        for photo in photos:
            validate_image(photo)
        return photos


class InterviewRejectForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        label='เหตุผลการปฏิเสธ',
        widget=forms.Textarea(attrs={'rows': 3}),
        error_messages={'required': 'กรุณาระบุเหตุผลการปฏิเสธ'},
    )


class InterviewResultForm(BootstrapFormMixin, forms.Form):
    outcome = forms.ChoiceField(
        label='ผลการสัมภาษณ์',
        choices=InterviewResult.OUTCOME_CHOICES,
        error_messages={'required': 'กรุณาเลือกผลการสัมภาษณ์'},
    )
    notes = forms.CharField(
        label='รายละเอียดผลการสัมภาษณ์',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณากรอกรายละเอียดผลการสัมภาษณ์'},
    )
    photos = MultipleFileField(
        label='รูปภาพการสัมภาษณ์ (1-5 รูป)',
        widget=MultipleFileInput(
            attrs={'multiple': True, 'accept': '.jpg,.jpeg,.png,image/*'}
        ),
        error_messages={'required': 'กรุณาอัปโหลดรูปภาพการสัมภาษณ์ 1-5 รูป'},
    )

    def clean_photos(self):
        photos = self.cleaned_data.get('photos') or []
        if not 1 <= len(photos) <= 5:
            raise ValidationError('กรุณาอัปโหลดรูปภาพการสัมภาษณ์ 1-5 รูป')
        for photo in photos:
            validate_image(photo)
        return photos


class ContractForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AdoptionContract
        fields = ('terms', 'start_date')
        widgets = {
            'terms': forms.Textarea(attrs={'rows': 10}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'terms': 'ข้อสัญญา',
            'start_date': 'วันเริ่มสัญญา',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['terms'].required = False
        self.fields['start_date'].required = False

    def clean_terms(self):
        return self.cleaned_data.get('terms') or DEFAULT_CONTRACT_TERMS

    def clean_start_date(self):
        return self.cleaned_data.get('start_date') or timezone.localdate()


class FollowUpSubmitForm(BootstrapFormMixin, forms.Form):
    notes = forms.CharField(
        label='หมายเหตุ',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
    )
    photos = MultipleFileField(
        label='รูปถ่ายที่อยู่อาศัย (1-5 รูป)',
        widget=MultipleFileInput(
            attrs={'multiple': True, 'accept': '.jpg,.jpeg,.png,image/*'}
        ),
        error_messages={'required': 'กรุณาอัปโหลดรูปถ่ายที่อยู่อาศัย 1-5 รูป'},
    )

    def clean_photos(self):
        photos = self.cleaned_data.get('photos') or []
        if not 1 <= len(photos) <= 5:
            raise ValidationError('กรุณาอัปโหลดรูปถ่ายที่อยู่อาศัย 1-5 รูป')
        for photo in photos:
            validate_image(photo)
        return photos


class HomeVisitForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = HomeVisit
        fields = ('scheduled_at', 'notes')
        widgets = {
            'scheduled_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'scheduled_at': 'วันและเวลาตรวจบ้าน',
            'notes': 'หมายเหตุ',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['scheduled_at'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data['scheduled_at']
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(
                scheduled_at, timezone.get_current_timezone()
            )
        if scheduled_at <= timezone.now():
            raise ValidationError('กรุณาเลือกวันและเวลาในอนาคต')
        return scheduled_at


class HomeVisitRescheduleForm(BootstrapFormMixin, forms.Form):
    requested_scheduled_at = forms.DateTimeField(
        label='วันและเวลาที่ต้องการเลื่อนไป',
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
        ),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'],
        error_messages={
            'required': 'กรุณาเลือกวันและเวลาที่ต้องการเลื่อนไป',
            'invalid': 'รูปแบบวันและเวลาไม่ถูกต้อง',
        },
    )
    reason = forms.CharField(
        label='เหตุผลการขอเลื่อนนัด',
        widget=forms.Textarea(attrs={'rows': 3}),
        error_messages={'required': 'กรุณาระบุเหตุผลการขอเลื่อนนัด'},
    )

    def clean_requested_scheduled_at(self):
        requested = self.cleaned_data['requested_scheduled_at']
        if timezone.is_naive(requested):
            requested = timezone.make_aware(
                requested, timezone.get_current_timezone()
            )
        if requested <= timezone.now():
            raise ValidationError('กรุณาเลือกวันและเวลาในอนาคต')
        return requested


class FollowUpEvaluationForm(BootstrapFormMixin, forms.Form):
    housing_condition = forms.CharField(
        label='สภาพที่อยู่อาศัย',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณาระบุสภาพที่อยู่อาศัย'},
    )
    dog_condition = forms.CharField(
        label='สภาพสุนัข',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณาระบุสภาพสุนัข'},
    )
    notes = forms.CharField(
        label='หมายเหตุ',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
    )
    photos = MultipleFileField(
        label='รูปภาพประกอบการประเมิน (1-5 รูป)',
        widget=MultipleFileInput(
            attrs={'multiple': True, 'accept': '.jpg,.jpeg,.png,image/*'}
        ),
        error_messages={'required': 'กรุณาอัปโหลดรูปภาพประกอบการประเมิน 1-5 รูป'},
    )

    def clean_photos(self):
        photos = self.cleaned_data.get('photos') or []
        if not 1 <= len(photos) <= 5:
            raise ValidationError('กรุณาอัปโหลดรูปภาพประกอบการประเมิน 1-5 รูป')
        for photo in photos:
            validate_image(photo)
        return photos
