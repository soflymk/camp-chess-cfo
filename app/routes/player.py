from flask import Blueprint, render_template
from flask_login import login_required, current_user
from .. import db
from ..models import Championship, Participant, Match

player_bp = Blueprint('player', __name__)


def _build_dashboard_data(user_id):
    """Calcula todos os dados necessários para o dashboard."""
    part_ids = [p.championship_id for p in
                Participant.query.filter_by(user_id=user_id).all()]

    if not part_ids:
        return dict(
            active_championships=[], all_championships=[],
            pending_matches=[], past_matches=[],
            featured=None, global_stats={'wins': 0, 'draws': 0, 'losses': 0, 'played': 0},
        )

    # Todos os campeonatos
    all_championships = (Championship.query
                         .filter(Championship.id.in_(part_ids))
                         .order_by(Championship.created_at.desc()).all())

    active_championships = [c for c in all_championships if c.status == 'active']

    # Partidas pendentes (todas)
    pending_matches = (Match.query
                       .filter(Match.championship_id.in_(part_ids),
                               Match.status.in_(['pending', 'awaiting_confirmation', 'inconsistent']),
                               db.or_(Match.player1_id == user_id, Match.player2_id == user_id))
                       .order_by(Match.created_at).all())

    # Histórico
    past_matches = (Match.query
                    .filter(Match.championship_id.in_(part_ids),
                            Match.status.in_(['completed', 'wo', 'bye']),
                            db.or_(Match.player1_id == user_id, Match.player2_id == user_id))
                    .order_by(Match.completed_at.desc()).limit(20).all())

    # Campeonato destaque: primeiro ativo
    featured = None
    next_match = None
    featured_standing = None

    if active_championships:
        fc = active_championships[0]
        featured = fc

        # Próxima partida no campeonato destaque
        next_match = next(
            (m for m in pending_matches if m.championship_id == fc.id), None
        )

        # Posição na tabela (round robin) ou rodada (elimination)
        if fc.format == 'round_robin':
            standings = fc.get_standings()
            for i, row in enumerate(standings, 1):
                if row['user'].id == user_id:
                    featured_standing = {'pos': i, 'total': len(standings), **row}
                    break
        else:
            featured_standing = {'round': fc.current_round}

    # Stats globais
    wins = draws = losses = 0
    for m in past_matches:
        label = m.player_result_label(user_id)
        if label == 'Vitória':
            wins += 1
        elif label == 'Empate':
            draws += 1
        else:
            losses += 1

    return dict(
        active_championships=active_championships,
        all_championships=all_championships,
        pending_matches=pending_matches,
        past_matches=past_matches,
        featured=featured,
        next_match=next_match,
        featured_standing=featured_standing,
        global_stats={'wins': wins, 'draws': draws, 'losses': losses,
                      'played': wins + draws + losses},
    )


@player_bp.route('/dashboard')
@login_required
def dashboard():
    data = _build_dashboard_data(current_user.id)
    return render_template('player/dashboard.html', **data)
