"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

if settings.DEBUG:
    # Only dog photos are public. Private uploads are served by the
    # permission-checked /files/<kind>/<id>/ view instead.
    urlpatterns += [
        path(
            'media/dogs/<path:path>',
            serve,
            {'document_root': settings.MEDIA_ROOT / 'dogs'},
        ),
    ]
