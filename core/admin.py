from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    AuditEvent,
    Dog,
    DogHealthRecord,
    Notification,
    Profile,
    ShelterSettings,
)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'target_username', 'target_id', 'actor_username')
    list_filter = ('action',)
    search_fields = ('target_username', 'actor_username')
    readonly_fields = (
        'actor', 'actor_username', 'action', 'target_id',
        'target_username', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Profile)
class ProfileAdmin(SimpleHistoryAdmin):
    # Django admin is a superuser/break-glass tool. Keep personal contact
    # details out of it; account owners manage them from ``my_profile``.
    list_display = ('user', 'pdpa_consent_at')
    search_fields = ('user__username',)
    fields = ('user', 'pdpa_consent_at')


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


@admin.register(Notification)
class NotificationAdmin(SimpleHistoryAdmin):
    list_display = ('title', 'user', 'status', 'attempts', 'next_attempt_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'user__username', 'dedupe_key')
    fields = (
        'user', 'title', 'status', 'attempts', 'dedupe_key', 'read_at',
        'next_attempt_at', 'created_at', 'updated_at',
    )
    readonly_fields = ('created_at', 'updated_at')
