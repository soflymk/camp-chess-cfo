from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .. import db
from ..services import audit

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/edit', methods=['POST'])
@login_required
def edit():
    name = request.form.get('name', '').strip()
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if name:
        current_user.name = name

    if new_pw:
        if not current_user.check_password(current_pw):
            flash('Senha atual incorreta.', 'danger')
            return redirect(request.referrer or url_for('auth.index'))
        if len(new_pw) < 6:
            flash('Nova senha deve ter ao menos 6 caracteres.', 'danger')
            return redirect(request.referrer or url_for('auth.index'))
        if new_pw != confirm_pw:
            flash('As senhas não conferem.', 'danger')
            return redirect(request.referrer or url_for('auth.index'))
        current_user.set_password(new_pw)

    db.session.commit()
    audit('profile_edit', f'{current_user.username} editou perfil', user_id=current_user.id)
    db.session.commit()
    flash('Perfil atualizado!', 'success')
    return redirect(request.referrer or url_for('auth.index'))
