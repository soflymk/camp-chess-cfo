from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from .. import db
from ..models import User, Championship, Participant, Match, AuditLog
from ..services import (audit, generate_bracket, generate_round_robin,
                        disqualify_player, try_advance_bracket,
                        check_round_robin_finished)

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    championships = Championship.query.order_by(Championship.created_at.desc()).all()
    users_count = User.query.count()
    inconsistent = Match.query.filter_by(status='inconsistent').all()
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()
    return render_template('admin/dashboard.html',
                           championships=championships,
                           users_count=users_count,
                           inconsistent=inconsistent,
                           recent_logs=recent_logs)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/<int:uid>/toggle-role', methods=['POST'])
@admin_required
def toggle_role(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        flash('Você não pode alterar seu próprio papel.', 'warning')
    else:
        user.role = 'admin' if user.role == 'player' else 'player'
        db.session.commit()
        audit('toggle_role', f'{user.username} → {user.role}', user_id=current_user.id)
        db.session.commit()
        flash(f'Papel de {user.username} alterado para {user.role}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:uid>/toggle-active', methods=['POST'])
@admin_required
def toggle_active(uid):
    user = User.query.get_or_404(uid)
    if user.id == current_user.id:
        flash('Você não pode desativar sua própria conta.', 'warning')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        audit('toggle_active', f'{user.username} active={user.is_active}', user_id=current_user.id)
        db.session.commit()
        flash(f'Conta de {user.username} {"ativada" if user.is_active else "desativada"}.', 'success')
    return redirect(url_for('admin.users'))


# ---------------------------------------------------------------------------
# Championship CRUD
# ---------------------------------------------------------------------------

@admin_bp.route('/championship/create', methods=['GET', 'POST'])
@admin_required
def championship_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        fmt = request.form.get('format', '')
        block = bool(request.form.get('block_on_inconsistency'))

        if not name or fmt not in ('elimination', 'round_robin'):
            flash('Preencha todos os campos obrigatórios.', 'danger')
            return render_template('admin/championship_form.html')

        c = Championship(
            name=name, description=description,
            format=fmt, created_by=current_user.id,
            block_on_inconsistency=block,
        )
        db.session.add(c)
        db.session.commit()
        audit('championship_create', f'#{c.id} {name}', user_id=current_user.id)
        db.session.commit()
        flash('Campeonato criado!', 'success')
        return redirect(url_for('admin.championship_detail', cid=c.id))
    return render_template('admin/championship_form.html')


@admin_bp.route('/championship/<int:cid>')
@admin_required
def championship_detail(cid):
    c = Championship.query.get_or_404(cid)
    all_users = User.query.filter_by(is_active=True).all()
    participant_ids = {p.user_id for p in c.participants}
    available_users = [u for u in all_users if u.id not in participant_ids]
    rounds = {}
    for m in c.matches.order_by(Match.round, Match.bracket_position).all():
        rounds.setdefault(m.round, []).append(m)
    inconsistent = c.matches.filter_by(status='inconsistent').all()
    return render_template('admin/championship_detail.html',
                           c=c, available_users=available_users,
                           rounds=rounds, inconsistent=inconsistent)


@admin_bp.route('/championship/<int:cid>/add-participant', methods=['POST'])
@admin_required
def add_participant(cid):
    c = Championship.query.get_or_404(cid)
    if c.status != 'draft':
        flash('Só é possível adicionar participantes antes de iniciar.', 'warning')
        return redirect(url_for('admin.championship_detail', cid=cid))
    uid = int(request.form.get('user_id', 0))
    user = User.query.get_or_404(uid)
    if Participant.query.filter_by(championship_id=cid, user_id=uid).first():
        flash('Jogador já inscrito.', 'warning')
    else:
        db.session.add(Participant(championship_id=cid, user_id=uid))
        db.session.commit()
        audit('add_participant', f'User {uid} added to #{cid}', user_id=current_user.id)
        db.session.commit()
        flash(f'{user.username} adicionado.', 'success')
    return redirect(url_for('admin.championship_detail', cid=cid))


@admin_bp.route('/championship/<int:cid>/remove-participant/<int:uid>', methods=['POST'])
@admin_required
def remove_participant(cid, uid):
    c = Championship.query.get_or_404(cid)
    if c.status != 'draft':
        flash('Campeonato já iniciado.', 'warning')
        return redirect(url_for('admin.championship_detail', cid=cid))
    p = Participant.query.filter_by(championship_id=cid, user_id=uid).first_or_404()
    db.session.delete(p)
    db.session.commit()
    audit('remove_participant', f'User {uid} removed from #{cid}', user_id=current_user.id)
    db.session.commit()
    flash('Participante removido.', 'success')
    return redirect(url_for('admin.championship_detail', cid=cid))


@admin_bp.route('/championship/<int:cid>/start', methods=['POST'])
@admin_required
def championship_start(cid):
    c = Championship.query.get_or_404(cid)
    if c.status != 'draft':
        flash('Campeonato não está em rascunho.', 'warning')
        return redirect(url_for('admin.championship_detail', cid=cid))

    if c.format == 'elimination':
        ok, msg = generate_bracket(c)
    else:
        ok, msg = generate_round_robin(c)

    if ok:
        db.session.commit()
        audit('championship_start', f'#{cid}', user_id=current_user.id)
        db.session.commit()
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('admin.championship_detail', cid=cid))


@admin_bp.route('/championship/<int:cid>/finish', methods=['POST'])
@admin_required
def championship_finish(cid):
    c = Championship.query.get_or_404(cid)
    if c.status != 'active':
        flash('Campeonato não está ativo.', 'warning')
        return redirect(url_for('admin.championship_detail', cid=cid))
    c.status = 'finished'
    from datetime import datetime
    c.finished_at = datetime.utcnow()
    if c.format == 'round_robin':
        standings = c.get_standings()
        if standings:
            c.winner_id = standings[0]['user'].id
    db.session.commit()
    audit('championship_finish', f'#{cid} manually finished', user_id=current_user.id)
    db.session.commit()
    flash('Campeonato finalizado.', 'success')
    return redirect(url_for('admin.championship_detail', cid=cid))


@admin_bp.route('/championship/<int:cid>/reset', methods=['POST'])
@admin_required
def championship_reset(cid):
    c = Championship.query.get_or_404(cid)
    Match.query.filter_by(championship_id=cid).delete()
    Participant.query.filter_by(championship_id=cid).update({
        'is_disqualified': False,
        'disqualified_at': None,
        'disqualification_reason': None,
    })
    c.status = 'draft'
    c.started_at = None
    c.finished_at = None
    c.winner_id = None
    c.current_round = 1
    db.session.commit()
    audit('championship_reset', f'#{cid}', user_id=current_user.id)
    db.session.commit()
    flash('Campeonato resetado para rascunho.', 'success')
    return redirect(url_for('admin.championship_detail', cid=cid))


# ---------------------------------------------------------------------------
# Disqualification
# ---------------------------------------------------------------------------

@admin_bp.route('/championship/<int:cid>/disqualify/<int:uid>', methods=['POST'])
@admin_required
def disqualify(cid, uid):
    c = Championship.query.get_or_404(cid)
    reason = request.form.get('reason', 'Desclassificado pelo administrador').strip()
    ok, msg = disqualify_player(c, uid, reason, current_user.id)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('admin.championship_detail', cid=cid))


# ---------------------------------------------------------------------------
# Match / Inconsistency resolution
# ---------------------------------------------------------------------------

@admin_bp.route('/match/<int:mid>/resolve', methods=['POST'])
@admin_required
def resolve_match(mid):
    m = Match.query.get_or_404(mid)
    result = request.form.get('result', '')
    if result not in ('player1_win', 'player2_win', 'draw'):
        flash('Resultado inválido.', 'danger')
        return redirect(url_for('admin.championship_detail', cid=m.championship_id))
    m.force_result(result)
    db.session.commit()
    audit('resolve_match', f'Match {mid} → {result}', user_id=current_user.id)
    db.session.commit()
    c = m.championship
    if c.format == 'elimination':
        try_advance_bracket(c)
    else:
        check_round_robin_finished(c)
    flash('Resultado definido pelo administrador.', 'success')
    return redirect(url_for('admin.championship_detail', cid=m.championship_id))
