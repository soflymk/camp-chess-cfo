import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models import User
from ..services import audit

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('player.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()
        if user and user.is_active and user.check_password(password):
            login_user(user, remember=bool(request.form.get('remember')))
            audit('login', f'User {user.username} logged in', user_id=user.id)
            db.session.commit()
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('auth.index'))
        flash('Usuário/email ou senha inválidos.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower() or None
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        error = None
        if not username or len(username) < 3:
            error = 'Username deve ter ao menos 3 caracteres.'
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            error = 'Username: apenas letras, números e _.'
        elif len(password) < 6:
            error = 'Senha deve ter ao menos 6 caracteres.'
        elif password != confirm:
            error = 'Senhas não conferem.'
        elif User.query.filter_by(username=username).first():
            error = 'Username já em uso.'
        elif email and User.query.filter_by(email=email).first():
            error = 'Email já cadastrado.'

        if error:
            flash(error, 'danger')
        else:
            user = User(username=username, name=name or None, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            audit('register', f'New user {username}', user_id=user.id)
            db.session.commit()
            flash('Cadastro realizado! Faça login.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    audit('logout', f'User {current_user.username} logged out', user_id=current_user.id)
    db.session.commit()
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))
