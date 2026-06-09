from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from ..models import Championship, Match, Participant

championship_bp = Blueprint('championship', __name__)


@championship_bp.route('/list')
@login_required
def list_championships():
    if current_user.is_admin:
        championships = Championship.query.order_by(Championship.created_at.desc()).all()
    else:
        part_ids = [p.championship_id for p in
                    Participant.query.filter_by(user_id=current_user.id).all()]
        championships = Championship.query.filter(
            Championship.id.in_(part_ids) if part_ids else Championship.id == -1
        ).order_by(Championship.created_at.desc()).all()
    return render_template('championship/list.html', championships=championships)


@championship_bp.route('/<int:cid>/bracket')
@login_required
def bracket(cid):
    c = Championship.query.get_or_404(cid)
    if c.format != 'elimination':
        abort(400)
    rounds = {}
    for m in c.matches.order_by(Match.round, Match.bracket_position).all():
        rounds.setdefault(m.round, []).append(m)
    total_rounds = max(rounds.keys()) if rounds else 0
    round_names = _round_names(total_rounds)
    return render_template('championship/bracket.html',
                           c=c, rounds=rounds,
                           total_rounds=total_rounds,
                           round_names=round_names)


@championship_bp.route('/<int:cid>/standings')
@login_required
def standings(cid):
    c = Championship.query.get_or_404(cid)
    if c.format != 'round_robin':
        abort(400)
    table = c.get_standings()
    rounds = {}
    for m in c.matches.order_by(Match.round, Match.id).all():
        rounds.setdefault(m.round, []).append(m)
    return render_template('championship/standings.html',
                           c=c, table=table, rounds=rounds)


def _round_names(total):
    names = {}
    for r in range(1, total + 1):
        remaining = total - r + 1
        if remaining == 1:
            names[r] = 'Final'
        elif remaining == 2:
            names[r] = 'Semifinal'
        elif remaining == 3:
            names[r] = 'Quartas de Final'
        else:
            names[r] = f'Rodada {r}'
    return names
