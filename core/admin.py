from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Assessment,
    Dog,
    DogHealthRecord,
    HousingPhoto,
    InterviewPhoto,
    InterviewRequest,
    InterviewResult,
    Notification,
    Profile,
    ShelterSettings,
)


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


@admin.register(InterviewRequest)
class InterviewRequestAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'dog', 'adopter', 'scheduled_at', 'status')
    list_filter = ('status', 'scheduled_at')
    search_fields = ('code', 'dog__name', 'full_name', 'adopter__username')
    readonly_fields = ('code',)


@admin.register(Assessment)
class AssessmentAdmin(SimpleHistoryAdmin):
    list_display = ('interview_request', 'housing_type', 'household_members')
    list_filter = ('housing_type', 'has_other_pets', 'agree_home_visit')


@admin.register(HousingPhoto)
class HousingPhotoAdmin(SimpleHistoryAdmin):
    list_display = ('interview_request', 'uploaded_at')


@admin.register(InterviewResult)
class InterviewResultAdmin(SimpleHistoryAdmin):
    list_display = ('interview_request', 'outcome', 'recorded_by', 'recorded_at')
    list_filter = ('outcome',)


@admin.register(InterviewPhoto)
class InterviewPhotoAdmin(SimpleHistoryAdmin):
    list_display = ('result', 'uploaded_at')


@admin.register(Notification)
class NotificationAdmin(SimpleHistoryAdmin):
    list_display = ('title', 'user', 'status', 'attempts', 'next_attempt_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'message', 'user__username', 'dedupe_key')
