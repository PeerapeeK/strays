from datetime import timedelta

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import RegexValidator
from django.utils import timezone

from .addresses import (
    address_is_valid,
    compose_address,
    district_names,
    province_names,
    subdistrict_names,
)
from .images import delete_stored_file, process_profile_photo
from .models import (
    Assessment,
    AdoptionContract,
    DEFAULT_CONTRACT_TERMS,
    Dog,
    DogHealthRecord,
    HomeVisit,
    InterviewResult,
    Profile,
    ShelterSettings,
)
from .permissions import ADOPTER, STAFF
from .scheduling import (
    booking_horizon_days,
    is_slot_aligned,
    slot_choice_groups,
)
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
    """Apply Bootstrap 5 classes and required markers to every widget."""

    required_css_class = 'required'

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
            if field.required:
                widget.attrs['required'] = 'required'
                widget.attrs['aria-required'] = 'true'
            else:
                widget.attrs.pop('required', None)
                widget.attrs.pop('aria-required', None)

    def full_clean(self):
        super().full_clean()
        for name, field in self.fields.items():
            if not self.errors.get(name):
                continue
            widget = field.widget
            existing = widget.attrs.get('class', '')
            if 'is-invalid' not in existing.split():
                widget.attrs['class'] = f'{existing} is-invalid'.strip()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class PasswordResetRequestForm(BootstrapFormMixin, PasswordResetForm):
    pass


class PasswordResetConfirmForm(BootstrapFormMixin, SetPasswordForm):
    pass


class RegistrationForm(BootstrapFormMixin, UserCreationForm):
    full_name = forms.CharField(label='ชื่อ-นามสกุล', max_length=150)
    phone = forms.CharField(label='เบอร์โทรศัพท์', max_length=20)
    address = forms.CharField(
        label='ที่อยู่', widget=forms.Textarea, required=False
    )
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
            profile.address = self.cleaned_data.get('address', '')
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


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    full_name = forms.CharField(label='ชื่อ-นามสกุล', max_length=150)
    phone = forms.CharField(
        label='เบอร์โทรศัพท์', max_length=20, required=False
    )
    address = forms.CharField(
        label='ที่อยู่', widget=forms.Textarea, required=False
    )
    remove_photo = forms.BooleanField(
        label='ลบรูปโปรไฟล์', required=False
    )

    class Meta:
        model = Profile
        fields = ('full_name', 'phone', 'address', 'photo')
        widgets = {
            'photo': forms.FileInput(
                attrs={'accept': '.jpg,.jpeg,.png,image/*'}
            ),
        }
        help_texts = {
            'photo': 'รับเฉพาะไฟล์ JPG, JPEG หรือ PNG ขนาดไม่เกิน 5 MB',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_photo = None
        if self.instance and self.instance.pk and self.instance.photo:
            self._old_photo = self.instance.photo
        if not self._old_photo:
            self.fields.pop('remove_photo', None)

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if isinstance(photo, UploadedFile):
            validate_image(photo)
        return photo

    def save(self, commit=True):
        old_photo = self._old_photo

        profile = super().save(commit=False)
        remove_photo = self.cleaned_data.get('remove_photo')
        new_photo = self.cleaned_data.get('photo')
        new_upload = isinstance(new_photo, UploadedFile)
        if remove_photo:
            profile.photo = ''
        elif new_upload:
            profile.photo = process_profile_photo(new_photo)

        if commit:
            profile.save()
            if old_photo and (remove_photo or new_upload):
                delete_stored_file(old_photo)
        return profile


class UserEditForm(BootstrapFormMixin, forms.ModelForm):
    """Admin account form.

    System administrators manage the account itself (username, email, active
    state). Personal/contact details stay with the account owner in
    ``my_profile`` and are deliberately not exposed here (least privilege).
    """

    username = forms.CharField(
        label='ชื่อผู้ใช้',
        max_length=150,
        validators=[
            RegexValidator(
                r'^[A-Za-z0-9@.+\-_]+$',
                'ชื่อผู้ใช้ใช้ได้เฉพาะตัวอักษรภาษาอังกฤษ ตัวเลข และ @ . + - _ เท่านั้น',
            )
        ],
        error_messages={'required': 'กรุณากรอกชื่อผู้ใช้'},
        help_text='ใช้ตัวอักษรภาษาอังกฤษ ตัวเลข และ @ . + - _ เท่านั้น',
    )
    remove_photo = forms.BooleanField(
        label='ลบรูปโปรไฟล์', required=False
    )

    class Meta:
        model = User
        fields = ('username', 'email')
        labels = {
            'email': 'อีเมล',
        }

    def __init__(self, *args, allow_remove_photo=False, **kwargs):
        super().__init__(*args, **kwargs)
        profile = None
        if self.instance and self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
        if not allow_remove_photo or not (profile and profile.photo):
            self.fields.pop('remove_photo', None)

    def clean_username(self):
        username = self.cleaned_data['username']
        if not username:
            raise ValidationError('กรุณากรอกชื่อผู้ใช้')
        duplicates = User.objects.filter(username__iexact=username)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise ValidationError('ชื่อผู้ใช้นี้ถูกใช้งานแล้ว')
        return username

    def save(self, commit=True):
        old_photo = None
        if self.instance.pk:
            profile = getattr(self.instance, 'profile', None)
            if profile and profile.photo:
                old_photo = profile.photo

        user = super().save(commit=commit)
        if commit:
            remove_photo = self.cleaned_data.get('remove_photo')
            if remove_photo and old_photo:
                profile = user.profile
                profile.photo = ''
                profile.save(update_fields=['photo'])
                delete_stored_file(old_photo)
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
            'intake_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'description': forms.Textarea(attrs={'rows': 4}),
            'photo': forms.ClearableFileInput(attrs={
                'accept': '.jpg,.jpeg,.png,image/*',
                'data-photo-preview': 'dog-photo-preview',
                'data-photo-error': 'dog-photo-error',
            }),
        }
        help_texts = {
            'name': 'ชื่อที่ใช้เรียกสุนัข',
            'breed': 'ระบุพันธุ์ หรือ "พันธุ์ผสม" หากไม่ทราบ',
            'sex': 'เลือกเพศของสุนัข',
            'age_months': 'ระบุอายุเป็นจำนวนเดือน',
            'size': 'ขนาดตัวเมื่อโตเต็มที่',
            'color': 'สีขนหรือลักษณะเด่น',
            'description': 'เล่าเรื่องราว ลักษณะนิสัย และข้อมูลที่ควรรู้',
            'vaccinated': 'ติ๊กหากได้รับวัคซีนครบตามกำหนด',
            'sterilized': 'ติ๊กหากทำหมันแล้ว',
            'status': 'สถานะการรับอุปการะปัจจุบัน',
            'photo': 'รับเฉพาะไฟล์ JPG, JPEG หรือ PNG ขนาดไม่เกิน 5 MB',
            'intake_date': 'วันที่รับสุนัขเข้าศูนย์',
        }


class DogHealthRecordForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DogHealthRecord
        fields = ('record_date', 'title', 'description', 'veterinarian')
        widgets = {
            'record_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
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
    address_detail = forms.CharField(
        label='รายละเอียดที่อยู่ (บ้านเลขที่/ถนน/ซอย)',
        widget=forms.Textarea,
        error_messages={'required': 'กรุณากรอกรายละเอียดที่อยู่'},
    )
    province = forms.ChoiceField(
        label='จังหวัด',
        choices=(),
        error_messages={
            'required': 'กรุณาเลือกจังหวัด',
            'invalid_choice': 'กรุณาเลือกจังหวัดจากรายการ',
        },
    )
    district = forms.ChoiceField(
        label='อำเภอ/เขต',
        choices=(),
        error_messages={
            'required': 'กรุณาเลือกอำเภอ/เขต',
            'invalid_choice': 'กรุณาเลือกอำเภอ/เขตจากรายการ',
        },
    )
    subdistrict = forms.ChoiceField(
        label='ตำบล/แขวง',
        choices=(),
        error_messages={
            'required': 'กรุณาเลือกตำบล/แขวง',
            'invalid_choice': 'กรุณาเลือกตำบล/แขวงจากรายการ',
        },
    )
    postal_code = forms.CharField(
        label='รหัสไปรษณีย์',
        max_length=5,
        min_length=5,
        validators=[
            RegexValidator(r'^\d{5}$', 'รหัสไปรษณีย์ต้องเป็นตัวเลข 5 หลัก')
        ],
        error_messages={
            'required': 'กรุณากรอกรหัสไปรษณีย์',
            'min_length': 'รหัสไปรษณีย์ต้องเป็นตัวเลข 5 หลัก',
            'max_length': 'รหัสไปรษณีย์ต้องเป็นตัวเลข 5 หลัก',
        },
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
        widget=forms.Select,
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

    HELP_TEXTS = {
        'full_name': 'ใช้ชื่อ-นามสกุลเดียวกับบัตรประชาชน',
        'phone': 'ระบุเบอร์โทรศัพท์ที่ติดต่อได้สะดวก',
        'address_detail': 'บ้านเลขที่ ถนน ซอย หรือรายละเอียดเพิ่มเติม',
        'province': 'เลือกจังหวัดตามที่อยู่ปัจจุบัน',
        'district': 'เลือกอำเภอ/เขตตามจังหวัดที่เลือก',
        'subdistrict': 'เลือกตำบล/แขวงตามอำเภอที่เลือก',
        'postal_code': 'กรอกรหัสไปรษณีย์ 5 หลัก',
        'housing_type': 'เลือกประเภทที่พักอาศัยที่ท่านอยู่ปัจจุบัน',
        'household_members': 'นับรวมตัวท่านเอง',
        'has_other_pets': 'เช่น สุนัข แมว หรือสัตว์เลี้ยงอื่น ๆ',
        'experience': 'อธิบายประสบการณ์การเลี้ยงสุนัข (ถ้ามี)',
        'motivation': 'เล่าเหตุผลและความพร้อมในการรับอุปการะ',
        'agree_home_visit': 'เจ้าหน้าที่อาจเข้าตรวจบ้านก่อนและหลังรับเลี้ยง',
        'scheduled_at': 'เลือกวันและเวลาที่ว่างในช่วงเปิดทำการของศูนย์',
        'housing_photos': 'รับเฉพาะไฟล์ JPG, JPEG หรือ PNG ขนาดไม่เกิน 5 MB ต่อรูป',
    }

    def __init__(self, *args, require_pdpa=False, **kwargs):
        super().__init__(*args, **kwargs)
        for name, text in self.HELP_TEXTS.items():
            if name in self.fields:
                self.fields[name].help_text = text

        self._configure_address_fields()
        self.fields['scheduled_at'].widget.choices = slot_choice_groups()

        self.fields['housing_photos'].widget.attrs.update({
            'data-photo-preview': 'housing-photo-preview',
            'data-photo-error': 'housing-photo-error',
        })
        if require_pdpa:
            self.fields['pdpa_consent'].required = True
        else:
            self.fields['pdpa_consent'].required = False
            self.fields['pdpa_consent'].disabled = True
            self.fields['pdpa_consent'].initial = True

    def _configure_address_fields(self):
        province = self.data.get('province') if self.is_bound else self.initial.get('province')
        district = self.data.get('district') if self.is_bound else self.initial.get('district')

        self.fields['province'].choices = [
            ('', 'เลือกจังหวัด')
        ] + [(name, name) for name in province_names()]

        district_choices = [('', 'เลือกอำเภอ/เขต')]
        if province in province_names():
            district_choices += [
                (name, name) for name in district_names(province)
            ]
        self.fields['district'].choices = district_choices

        subdistrict_choices = [('', 'เลือกตำบล/แขวง')]
        if (
            province in province_names()
            and district in district_names(province)
        ):
            subdistrict_choices += [
                (name, name)
                for name in subdistrict_names(province, district)
            ]
        self.fields['subdistrict'].choices = subdistrict_choices

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get('province')
        district = cleaned.get('district')
        subdistrict = cleaned.get('subdistrict')
        postal_code = cleaned.get('postal_code')
        if province and district and subdistrict and postal_code:
            if not address_is_valid(
                province, district, subdistrict, postal_code
            ):
                raise ValidationError(
                    'จังหวัด อำเภอ/เขต ตำบล/แขวง และรหัสไปรษณีย์ '
                    'ไม่สอดคล้องกัน กรุณาตรวจสอบอีกครั้ง'
                )
        return cleaned

    def get_full_address(self):
        data = self.cleaned_data
        return compose_address(
            data.get('address_detail', ''),
            data.get('subdistrict', ''),
            data.get('district', ''),
            data.get('province', ''),
            data.get('postal_code', ''),
        )

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data['scheduled_at']
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(
                scheduled_at, timezone.get_current_timezone()
            )
        if scheduled_at <= timezone.now():
            raise ValidationError('กรุณาเลือกวันและเวลาในอนาคต')

        shelter = ShelterSettings.load()
        local = timezone.localtime(scheduled_at)
        if not (shelter.opening_time <= local.time() < shelter.closing_time):
            raise ValidationError(
                'กรุณาเลือกเวลาในช่วงเปิดทำการ '
                f'{shelter.opening_time:%H:%M}-{shelter.closing_time:%H:%M} น.'
            )

        horizon_end = timezone.localdate() + timedelta(
            days=booking_horizon_days()
        )
        if local.date() > horizon_end:
            raise ValidationError(
                'สามารถจองคิวล่วงหน้าได้ไม่เกิน '
                f'{booking_horizon_days()} วัน'
            )

        if not is_slot_aligned(scheduled_at, shelter=shelter):
            raise ValidationError(
                'กรุณาเลือกเวลาให้ตรงกับช่วงเวลานัดหมายที่ระบบกำหนด'
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
            'start_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
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
        help_text='อธิบายสภาพความเป็นอยู่ของสุนัขโดยย่อ (ไม่บังคับ)',
    )
    photos = MultipleFileField(
        label='รูปถ่ายที่อยู่อาศัย (1-5 รูป)',
        widget=MultipleFileInput(
            attrs={
                'multiple': True,
                'accept': '.jpg,.jpeg,.png,image/*',
                'data-photo-preview': 'followup-photo-preview',
                'data-photo-error': 'followup-photo-error',
            }
        ),
        help_text='รับเฉพาะไฟล์ JPG, JPEG หรือ PNG ขนาดไม่เกิน 5 MB ต่อรูป',
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
