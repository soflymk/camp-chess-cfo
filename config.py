import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _build_db_url():
    raw = os.environ.get('DATABASE_URL', '').strip()

    # Render às vezes seta DATABASE_URL como string vazia ou "None"
    if not raw or raw.lower() == 'none':
        instance_dir = os.path.join(basedir, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        return f'sqlite:///{os.path.join(instance_dir, "app.db")}'

    # Render usa postgres://, SQLAlchemy 2.x exige postgresql://
    if raw.startswith('postgres://'):
        raw = raw.replace('postgres://', 'postgresql://', 1)

    return raw


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = _build_db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig,
}
