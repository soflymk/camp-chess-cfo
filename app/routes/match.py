from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, abort, jsonify)
from flask_login import login_required, current_user
from .. import db
from ..models import Match, MatchMessage
from ..services import audit, try_advance_bracket, check_round_robin_finished

match_bp = Blueprint('match', __name__)

_ALLOWED_LINK_PREFIXES = (
    'https://lichess.org/',
    'https://www.chess.com/',
    'https://chess.com/',
)


def _can_access(m):
    return current_user.is_admin or current_user.id in (m.player1_id, m.player2_id)


@match_bp.route('/<int:mid>')
@login_required
def detail(mid):
    m = Match.query.get_or_404(mid)
    if not _can_access(m):
        abort(403)
    already_reported = None
    if current_user.id == m.player1_id:
        already_reported = m.player1_reported
    elif current_user.id == m.player2_id:
        already_reported = m.player2_reported
    messages = m.messages.order_by(MatchMessage.created_at).all()
    return render_template('match/detail.html', m=m,
                           already_reported=already_reported,
                           messages=messages)


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
        flash('Resultado confirmado! ✅', 'success')
        c = m.championship
        if c.format == 'elimination':
            try_advance_bracket(c)
        else:
            check_round_robin_finished(c)
    elif m.status == 'inconsistent':
        flash('Resultado inconsistente! O administrador foi alertado.', 'warning')
    else:
        flash('Resultado registrado. Aguardando confirmação do adversário.', 'info')

    return redirect(url_for('match.detail', mid=mid))


# ── Chat ──────────────────────────────────────────────────────────────────────

@match_bp.route('/<int:mid>/messages')
@login_required
def get_messages(mid):
    m = Match.query.get_or_404(mid)
    if not _can_access(m):
        abort(403)
    after = request.args.get('after', 0, type=int)
    msgs = (MatchMessage.query
            .filter_by(match_id=mid)
            .filter(MatchMessage.id > after)
            .order_by(MatchMessage.created_at)
            .limit(100)
            .all())
    return jsonify({'messages': [msg.to_dict(current_user.id) for msg in msgs]})


@match_bp.route('/<int:mid>/message', methods=['POST'])
@login_required
def post_message(mid):
    m = Match.query.get_or_404(mid)
    if not _can_access(m):
        abort(403)
    text = request.form.get('message', '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'Mensagem vazia'}), 400
    if len(text) > 500:
        return jsonify({'ok': False, 'error': 'Mensagem muito longa'}), 400

    msg = MatchMessage(match_id=mid, user_id=current_user.id, message=text)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'ok': True, 'id': msg.id})


# ── Invite Link ───────────────────────────────────────────────────────────────

@match_bp.route('/<int:mid>/invite-link', methods=['POST'])
@login_required
def set_invite_link(mid):
    m = Match.query.get_or_404(mid)
    if not _can_access(m):
        abort(403)
    link = request.form.get('invite_link', '').strip()
    if link and not any(link.startswith(p) for p in _ALLOWED_LINK_PREFIXES):
        flash('Link inválido. Use chess.com ou lichess.org.', 'danger')
        return redirect(url_for('match.detail', mid=mid))
    m.invite_link = link or None
    db.session.commit()
    flash('Link atualizado!', 'success')
    return redirect(url_for('match.detail', mid=mid))
