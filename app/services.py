"""Business logic: bracket generation, round robin, audit, W.O."""
import math
import random
from datetime import datetime
from flask import request
from . import db
from .models import Match, Championship, Participant, AuditLog, User


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit(action, details='', user_id=None):
    ip = request.remote_addr if request else None
    log = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip)
    db.session.add(log)


# ---------------------------------------------------------------------------
# Elimination bracket
# ---------------------------------------------------------------------------

def generate_bracket(championship: Championship):
    participants = championship.get_active_participants()
    random.shuffle(participants)
    n = len(participants)
    if n < 2:
        return False, 'Mínimo de 2 participantes necessário.'

    next_pow2 = 1
    while next_pow2 < n:
        next_pow2 *= 2

    seeds = list(participants) + [None] * (next_pow2 - n)

    for i in range(0, next_pow2, 2):
        p1 = seeds[i]
        p2 = seeds[i + 1] if i + 1 < next_pow2 else None
        is_bye = p1 is None or p2 is None
        m = Match(
            championship_id=championship.id,
            player1_id=p1.user_id if p1 else None,
            player2_id=p2.user_id if p2 else None,
            round=1,
            bracket_position=i // 2,
            is_bye=is_bye,
            status='completed' if is_bye else 'pending',
        )
        if is_bye:
            m.final_result = 'player1_win' if p1 else 'player2_win'
            m.completed_at = datetime.utcnow()
        db.session.add(m)

    championship.current_round = 1
    championship.status = 'active'
    championship.started_at = datetime.utcnow()
    return True, 'Bracket gerado.'


def try_advance_bracket(championship: Championship):
    """Check if current round is done; if so generate next round or finish."""
    if championship.block_on_inconsistency and championship.has_inconsistencies():
        return

    round_matches = Match.query.filter_by(
        championship_id=championship.id,
        round=championship.current_round,
    ).all()

    incomplete = [m for m in round_matches if m.status not in ('completed', 'bye', 'wo')]
    if incomplete:
        return

    winners = [m.get_winner_id() for m in round_matches]
    winners = [w for w in winners if w is not None]

    if len(winners) <= 1:
        championship.status = 'finished'
        championship.finished_at = datetime.utcnow()
        if winners:
            championship.winner_id = winners[0]
        db.session.commit()
        return

    next_round = championship.current_round + 1
    championship.current_round = next_round

    for i in range(0, len(winners), 2):
        p1_id = winners[i]
        p2_id = winners[i + 1] if i + 1 < len(winners) else None
        is_bye = p2_id is None
        m = Match(
            championship_id=championship.id,
            player1_id=p1_id,
            player2_id=p2_id,
            round=next_round,
            bracket_position=i // 2,
            is_bye=is_bye,
            status='completed' if is_bye else 'pending',
        )
        if is_bye:
            m.final_result = 'player1_win'
            m.completed_at = datetime.utcnow()
        db.session.add(m)

    db.session.commit()


# ---------------------------------------------------------------------------
# Round Robin
# ---------------------------------------------------------------------------

def generate_round_robin(championship: Championship):
    participants = championship.get_active_participants()
    n = len(participants)
    if n < 2:
        return False, 'Mínimo de 2 participantes necessário.'

    # Circle method scheduling
    lst = list(participants)
    if n % 2 == 1:
        lst.append(None)  # BYE placeholder

    total_rounds = len(lst) - 1
    half = len(lst) // 2
    round_num = 1

    for _ in range(total_rounds):
        for i in range(half):
            p1 = lst[i]
            p2 = lst[len(lst) - 1 - i]
            if p1 is None or p2 is None:
                pass  # skip BYE slots
            else:
                m = Match(
                    championship_id=championship.id,
                    player1_id=p1.user_id,
                    player2_id=p2.user_id,
                    round=round_num,
                    status='pending',
                )
                db.session.add(m)
        # Rotate keeping lst[0] fixed
        lst = [lst[0]] + [lst[-1]] + lst[1:-1]
        round_num += 1

    championship.current_round = 1
    championship.status = 'active'
    championship.started_at = datetime.utcnow()
    return True, 'Confrontos gerados.'


def check_round_robin_finished(championship: Championship):
    pending = Match.query.filter_by(
        championship_id=championship.id,
    ).filter(Match.status.notin_(['completed', 'wo'])).count()
    if pending == 0:
        championship.status = 'finished'
        championship.finished_at = datetime.utcnow()
        standings = championship.get_standings()
        if standings:
            championship.winner_id = standings[0]['user'].id
        db.session.commit()


# ---------------------------------------------------------------------------
# Disqualification
# ---------------------------------------------------------------------------

def disqualify_player(championship: Championship, user_id: int, reason: str, admin_id: int):
    participant = Participant.query.filter_by(
        championship_id=championship.id,
        user_id=user_id,
    ).first()
    if not participant or participant.is_disqualified:
        return False, 'Participante não encontrado ou já desclassificado.'

    participant.is_disqualified = True
    participant.disqualified_at = datetime.utcnow()
    participant.disqualification_reason = reason

    # Apply W.O. to all pending / awaiting matches
    pending_matches = Match.query.filter(
        Match.championship_id == championship.id,
        Match.status.in_(['pending', 'awaiting_confirmation', 'inconsistent']),
        db.or_(Match.player1_id == user_id, Match.player2_id == user_id),
    ).all()

    for m in pending_matches:
        m.apply_wo(user_id)

    db.session.commit()

    audit('disqualify_player',
          f'User {user_id} disqualified from championship {championship.id}: {reason}',
          user_id=admin_id)

    if championship.format == 'elimination':
        try_advance_bracket(championship)
    else:
        check_round_robin_finished(championship)

    return True, 'Jogador desclassificado.'
