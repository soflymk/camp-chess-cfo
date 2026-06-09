import os
from app import create_app, db

app = create_app(os.getenv('FLASK_ENV', 'production'))


@app.cli.command('init-db')
def init_db():
    """Create all database tables."""
    with app.app_context():
        db.create_all()
        print('Database initialized.')


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
