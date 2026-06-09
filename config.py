import os


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')

    _db_url = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url
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
