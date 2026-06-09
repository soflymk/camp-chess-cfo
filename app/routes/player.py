from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .. import db
from ..models import Championship, Participant, Match

player_bp = Blueprint('player', __name__)


@player_bp.route('/dashboard')
@login_required
def dashboard():
    participations = Participant.query.filter_by(user_id=current_user.id).all()
    championship_ids = [p.championship_id for p in participations]

    active_championships = Championship.query.filter(
        Championship.id.in_(championship_ids),
        Championship.status == 'active',
    ).all() if championship_ids else []

    pending_matches = Match.query.filter(
        Match.championship_id.in_(championship_ids),
        Match.status.in_(['pending', 'awaiting_confirmation', 'inconsistent']),
        db.or_(Match.player1_id == current_user.id, Match.player2_id == current_user.id),
    ).order_by(Match.created_at.desc()).all() if championship_ids else []

    past_matches = Match.query.filter(
        Match.championship_id.in_(championship_ids),
        Match.status.in_(['completed', 'wo', 'bye']),
        db.or_(Match.player1_id == current_user.id, Match.player2_id == current_user.id),
    ).order_by(Match.completed_at.desc()).limit(20).all() if championship_ids else []

    all_championships = Championship.query.filter(
        Championship.id.in_(championship_ids),
    ).order_by(Championship.created_at.desc()).all() if championship_ids else []

    return render_template('player/dashboard.html',
                           active_championships=active_championships,
                           pending_matches=pending_matches,
                           past_matches=past_matches,
                           all_championships=all_championships)
