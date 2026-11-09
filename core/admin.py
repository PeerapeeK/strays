from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Dog, DogHealthRecord, Profile, ShelterSettings


@admin.register(Profile)
class ProfileAdmin(SimpleHistoryAdmin):
    list_display = ('user', 'full_name', 'phone', 'pdpa_consent_at')
    search_fields = ('user__username', 'full_name', 'phone')


@admin.register(ShelterSettings)
class ShelterSettingsAdmin(SimpleHistoryAdmin):
    list_display = ('opening_time', 'closing_time')

    def has_add_permission(self, request):
        return not ShelterSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Dog)
class DogAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'breed', 'sex', 'size', 'status', 'intake_date')
    list_filter = ('status', 'sex', 'size', 'vaccinated', 'sterilized')
    search_fields = ('name', 'breed', 'color', 'description')


@admin.register(DogHealthRecord)
class DogHealthRecordAdmin(SimpleHistoryAdmin):
    list_display = ('dog', 'record_date', 'title', 'veterinarian')
    list_filter = ('record_date',)
    search_fields = ('dog__name', 'title', 'description', 'veterinarian')
