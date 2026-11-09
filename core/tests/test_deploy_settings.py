import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parents[2]

SETTINGS_KEYS = (
    'DEBUG',
    'SECRET_KEY',
    'ALLOWED_HOSTS',
    'CSRF_TRUSTED_ORIGINS',
    'SECURE_PROXY_SSL_HEADER',
    'SESSION_COOKIE_SECURE',
    'CSRF_COOKIE_SECURE',
    'SECURE_HSTS_SECONDS',
    'SECURE_CONTENT_TYPE_NOSNIFF',
    'X_FRAME_OPTIONS',
    'STATIC_ROOT',
)

PROBE = """
import json
import config.settings as settings
print(json.dumps({
    "DEBUG": settings.DEBUG,
    "SECRET_KEY": settings.SECRET_KEY,
    "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
    "CSRF_TRUSTED_ORIGINS": settings.CSRF_TRUSTED_ORIGINS,
    "SECURE_PROXY_SSL_HEADER": getattr(
        settings, "SECURE_PROXY_SSL_HEADER", None
    ),
    "SESSION_COOKIE_SECURE": getattr(
        settings, "SESSION_COOKIE_SECURE", False
    ),
    "CSRF_COOKIE_SECURE": getattr(settings, "CSRF_COOKIE_SECURE", False),
    "SECURE_HSTS_SECONDS": getattr(settings, "SECURE_HSTS_SECONDS", 0),
    "SECURE_CONTENT_TYPE_NOSNIFF": getattr(
        settings, "SECURE_CONTENT_TYPE_NOSNIFF", False
    ),
    "X_FRAME_OPTIONS": getattr(settings, "X_FRAME_OPTIONS", None),
    "STATIC_ROOT": str(settings.STATIC_ROOT),
}))
"""


class ProductionSettingsTests(SimpleTestCase):
    def run_settings_probe(self, **env_overrides):
        env = os.environ.copy()
        for key in SETTINGS_KEYS:
            env.pop(key, None)
        env.pop('SECURE_SSL_REDIRECT', None)
        env.pop('SECURE_HSTS_INCLUDE_SUBDOMAINS', None)
        env.pop('SECURE_HSTS_PRELOAD', None)
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, '-c', PROBE],
            cwd=str(BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_missing_secret_key_fails_when_debug_is_false(self):
        result = self.run_settings_probe(DEBUG='False')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY', result.stderr)

    def test_development_has_a_safe_fallback(self):
        result = self.run_settings_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['DEBUG'])
        self.assertTrue(data['SECRET_KEY'].startswith('django-insecure-'))

    def test_production_hardening_and_env_parsing(self):
        result = self.run_settings_probe(
            DEBUG='False',
            SECRET_KEY='x' * 60,
            ALLOWED_HOSTS='strays.peerapeek.cc, localhost',
            CSRF_TRUSTED_ORIGINS='https://strays.peerapeek.cc',
            SECURE_HSTS_SECONDS='7200',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)

        self.assertFalse(data['DEBUG'])
        self.assertEqual(data['SECRET_KEY'], 'x' * 60)
        self.assertEqual(
            data['ALLOWED_HOSTS'], ['strays.peerapeek.cc', 'localhost']
        )
        self.assertEqual(
            data['CSRF_TRUSTED_ORIGINS'],
            ['https://strays.peerapeek.cc'],
        )
        self.assertEqual(
            data['SECURE_PROXY_SSL_HEADER'],
            ['HTTP_X_FORWARDED_PROTO', 'https'],
        )
        self.assertTrue(data['SESSION_COOKIE_SECURE'])
        self.assertTrue(data['CSRF_COOKIE_SECURE'])
        self.assertEqual(data['SECURE_HSTS_SECONDS'], 7200)
        self.assertTrue(data['SECURE_CONTENT_TYPE_NOSNIFF'])
        self.assertEqual(data['X_FRAME_OPTIONS'], 'DENY')
        self.assertEqual(
            data['STATIC_ROOT'], str(BASE_DIR / 'staticfiles')
        )

    def test_hsts_defaults_to_one_hour(self):
        result = self.run_settings_probe(
            DEBUG='False',
            SECRET_KEY='x' * 60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['SECURE_HSTS_SECONDS'], 3600)
