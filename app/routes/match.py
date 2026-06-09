from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from .. import db
from ..models import Match
from ..services import audit, try_advance_bracket, check_round_robin_finished

match_bp = Blueprint('match', __name__)


@match_bp.route('/<int:mid>')
@login_required
def detail(mid):
    m = Match.query.get_or_404(mid)
    # Access check: admin or participant
    if not current_user.is_admin and \
       current_user.id not in (m.player1_id, m.player2_id):
        abort(403)
    already_reported = None
    if current_user.id == m.player1_id:
        already_reported = m.player1_reported
    elif current_user.id == m.player2_id:
        already_reported = m.player2_reported
    return render_template('match/detail.html', m=m, already_reported=already_reported)


@match_bp.route('/<int:mid>/submit', methods=['POST'])
@login_required
def submit_result(mid):
    m = Match.query.get_or_404(mid)
    if current_user.id not in (m.player1_id, m.player2_id):
        abort(403)

    result = request.form.get('result', '')
    if result not in ('win', 'loss', 'draw'):
        flash('Resultado inválido.', 'danger')
        return redirect(url_for('match.detail', mid=mid))

    ok, msg = m.submit_result(current_user.id, result)
    if not ok:
        flash(msg, 'danger')
        return redirect(url_for('match.detail', mid=mid))

    db.session.commit()
    audit('submit_result',
          f'Match {mid}: user {current_user.id} reported {result}',
          user_id=current_user.id)
    db.session.commit()

    if m.status == 'completed':
        flash('Resultado confirmado!', 'success')
        c = m.championship
        if c.format == 'elimination':
            try_advance_bracket(c)
        else:
            check_round_robin_finished(c)
    elif m.status == 'inconsistent':
        flash('Resultado inconsistente! O administrador foi alertado.', 'warning')
    else:
        flash('Resultado registrado. Aguardando confirmação do adversário.', 'info')

    return redirect(url_for('player.dashboard'))
