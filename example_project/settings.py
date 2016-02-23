# Django settings for example_project project.

import os
import sys
import yaml

# Path to here is something like
# /data/vhost/<vhost>/<repo>/<project_name>/settings/base.py
SETTINGS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SETTINGS_DIR, '..'))
PARENT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, '..'))

CACHE_ROOT = PROJECT_ROOT

config_file = os.path.join(PROJECT_ROOT, 'conf', 'general.yml')
with open(config_file) as f:
        config = yaml.load(f)

PMG_COMMITTEE_USER = config.get('PMG_COMMITTEE_USER')
PMG_COMMITTEE_PASS = config.get('PMG_COMMITTEE_PASS')

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

HANSARD_CACHE = os.path.join(PROJECT_ROOT, 'hansard_cache/')
COMMITTEE_CACHE = os.path.join(PROJECT_ROOT, 'hansard_cache/committee/')
ANSWER_CACHE = os.path.join(PROJECT_ROOT, 'hansard_cache/answers/')
QUESTION_CACHE = os.path.join(PROJECT_ROOT, 'hansard_cache/questions/')
ANSWER_JSON_CACHE = os.path.join(PROJECT_ROOT, 'hansard_cache/answers_json/')
QUESTION_JSON_CACHE = os.path.join(PROJECT_ROOT, 'hansard_cache/questions_json/')

HTTPLIB2_CACHE_DIR = os.path.join(PROJECT_ROOT, 'httplib2_cache/')

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': config.get('ZAH_DB_NAME', ''),
        # The following settings are not used with sqlite3:
        'USER': config.get('ZAH_DB_USER', ''),
        'PASSWORD': config.get('ZAH_DB_PASS', ''),
        'HOST': config.get('ZAH_DB_HOST', ''), # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': config.get('ZAH_DB_PORT', ''), # Set to empty string for default.
    }
}

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# In a Windows environment this must be set to your system time zone.
TIME_ZONE = 'Africa/Johannesburg'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-uk'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = ''

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = ''

# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'dri5l8fh#4v7ypl0c=b4yj7zmg#bo-4$=8_^dyz2m3_c1&jw)#'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'example_project.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'example_project.wsgi.application'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

NOSE_ARGS = ['--with-doctest']

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_nose',
    'za_hansard',
    'speeches',
    'instances',
    'popolo',
    'popolo_name_resolver',
    'haystack',
    # Uncomment the next line to enable the admin:
    # 'django.contrib.admin',
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        }
    },
    'loggers': {
        'south': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'request': {
            'handlers': ['console'],
            'level': 'WARN',
            'propagate': True,
        },
        'pyelasticsearch': {
            'handlers': ['console'],
            'level': 'WARN',
            'propagate': True,
        },
        'requests.packages.urllib3.connectionpool': {
            'handlers': ['console'],
            'level': 'WARN',
            'propagate': True,
        },
    },
}

# Haystack config, needed by popolo-name-resolver
SEARCH_INDEX_NAME = DATABASES['default']['NAME']
if 'test' in sys.argv:
    SEARCH_INDEX_NAME += '_test'
HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': SEARCH_INDEX_NAME,
    },
}
