from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
        'TEST': {
            'NAME': 'postgres',  # Use the same database
            'OPTIONS': {
                'options': '-c search_path=pg_temp'  # Use temporary schema
            }
        }
    }
}
