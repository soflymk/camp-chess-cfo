import os

basedir = os.path.abspath(os.path.dirname(__file__))


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

    # Usa pg8000 como driver (puro Python, compatível com Python 3.14+)
    # Substitui postgresql:// → postgresql+pg8000://
    if raw.startswith('postgresql://'):
        raw = raw.replace('postgresql://', 'postgresql+pg8000://', 1)

    return raw


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = _build_db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,        # reconecta automaticamente
        'pool_recycle': 300,          # recicla conexões a cada 5 min
    }


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig,
}
