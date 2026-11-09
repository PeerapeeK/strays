from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User
from django.utils import timezone

from .permissions import ADOPTER, STAFF


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
