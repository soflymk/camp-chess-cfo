import os
import ssl
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

basedir = os.path.abspath(os.path.dirname(__file__))

# Parâmetros de query que pg8000 não aceita na URL
_PG8000_UNSUPPORTED_PARAMS = {'sslmode', 'channel_binding', 'sslrootcert',
                               'sslcert', 'sslkey', 'connect_timeout'}


def _build_db_url():
    raw = os.environ.get('DATABASE_URL', '').strip()

    # Sem DATABASE_URL → SQLite local
    if not raw or raw.lower() == 'none':
        instance_dir = os.path.join(basedir, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        return f'sqlite:///{os.path.join(instance_dir, "app.db")}'

    # Render/Heroku usam postgres://, SQLAlchemy exige postgresql://
    if raw.startswith('postgres://'):
        raw = raw.replace('postgres://', 'postgresql://', 1)

    if raw.startswith('postgresql://'):
        # Remove parâmetros incompatíveis com pg8000
        parsed = urlparse(raw)
        params = parse_qs(parsed.query, keep_blank_values=True)
        for key in _PG8000_UNSUPPORTED_PARAMS:
            params.pop(key, None)
        clean_query = urlencode({k: v[0] for k, v in params.items()})
        parsed = parsed._replace(query=clean_query)
        raw = urlunparse(parsed)
        # Injeta driver pg8000
        raw = raw.replace('postgresql://', 'postgresql+pg8000://', 1)

    return raw


def _needs_ssl():
    """Verifica se a URL original pede SSL."""
    raw = os.environ.get('DATABASE_URL', '')
    return 'sslmode=require' in raw or 'sslmode=verify' in raw


def _build_engine_options():
    opts = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    if _needs_ssl():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opts['connect_args'] = {'ssl_context': ctx}
    return opts


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = _build_db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _build_engine_options()


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig,
}
