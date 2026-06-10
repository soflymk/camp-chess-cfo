import json
import urllib.request
from datetime import datetime
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
_CHESS_UA = 'CFO-Chess-App/1.0'


def _can_access(m):
    return current_user.is_admin or current_user.id in (m.player1_id, m.player2_id)

def _is_ajax():
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


# ── Detail ────────────────────────────────────────────────────────────────────

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


# ── Submit result ─────────────────────────────────────────────────────────────

@match_bp.route('/<int:mid>/submit', methods=['POST'])
@login_required
def submit_result(mid):
    m = Match.query.get_or_404(mid)
    if current_user.id not in (m.player1_id, m.player2_id):
        if _is_ajax():
            return jsonify({'ok': False, 'error': 'Você não é participante desta partida.'})
        abort(403)

    result = request.form.get('result', '')
    if result not in ('win', 'loss', 'draw'):
        if _is_ajax():
            return jsonify({'ok': False, 'error': 'Resultado inválido.'})
        flash('Resultado inválido.', 'danger')
        return redirect(url_for('match.detail', mid=mid))

    ok, msg = m.submit_result(current_user.id, result)
    if not ok:
        if _is_ajax():
            return jsonify({'ok': False, 'error': msg})
        flash(msg, 'danger')
        return redirect(url_for('match.detail', mid=mid))

    db.session.commit()
    audit('submit_result',
          f'Match {mid}: user {current_user.id} reported {result}',
          user_id=current_user.id)
    db.session.commit()

    if m.status == 'completed':
        status_msg = 'Resultado confirmado! ✅'
        c = m.championship
        if c.format == 'elimination':
            try_advance_bracket(c)
        else:
            check_round_robin_finished(c)
    elif m.status == 'inconsistent':
        status_msg = 'Resultado inconsistente. O administrador foi alertado. ⚠️'
    else:
        status_msg = 'Resultado registrado. Aguardando confirmação do adversário. 🕐'

    if _is_ajax():
        return jsonify({'ok': True, 'message': status_msg, 'match_status': m.status})

    flash(status_msg, 'success' if m.status == 'completed' else
          'warning' if m.status == 'inconsistent' else 'info')
    return redirect(url_for('match.detail', mid=mid))


# ── Chess.com: verificar resultado automaticamente ────────────────────────────

@match_bp.route('/<int:mid>/check-result')
@login_required
def check_chess_result(mid):
    """Consulta a API do chess.com para detectar o resultado da partida."""
    m = Match.query.get_or_404(mid)
    if current_user.id not in (m.player1_id, m.player2_id):
        return jsonify({'ok': False, 'error': 'Você não é participante desta partida.'})

    p1_chess = m.player1.chess_username if m.player1 else None
    p2_chess = m.player2.chess_username if m.player2 else None

    if not p1_chess or not p2_chess:
        return jsonify({'ok': False,
                        'error': 'Um ou ambos os jogadores não configuraram o username do chess.com.'})

    if current_user.id == m.player1_id:
        my_chess, opp_chess = p1_chess, p2_chess
    else:
        my_chess, opp_chess = p2_chess, p1_chess

    match_ts = m.created_at.timestamp()
    now = datetime.utcnow()

    # Busca no mês atual e no anterior
    months = [(now.year, now.month)]
    if now.month == 1:
        months.append((now.year - 1, 12))
    else:
        months.append((now.year, now.month - 1))

    games_found = []
    for year, month in months:
        url = f'https://api.chess.com/pub/player/{my_chess}/games/{year}/{month:02d}'
        try:
            req = urllib.request.Request(url, headers={'User-Agent': _CHESS_UA})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            for g in data.get('games', []):
                white = g.get('white', {}).get('username', '').lower()
                black = g.get('black', {}).get('username', '').lower()
                if opp_chess.lower() not in (white, black):
                    continue
                if g.get('end_time', 0) < match_ts:
                    continue
                games_found.append(g)
        except Exception:
            pass

    if not games_found:
        return jsonify({'ok': False,
                        'error': 'Nenhuma partida encontrada no chess.com entre vocês após a criação desta partida.'})

    # Usa a partida mais recente
    games_found.sort(key=lambda g: g.get('end_time', 0), reverse=True)
    game = games_found[0]

    my_lower = my_chess.lower()
    white_user = game.get('white', {}).get('username', '').lower()

    if my_lower == white_user:
        my_result_raw = game.get('white', {}).get('result', '')
    else:
        my_result_raw = game.get('black', {}).get('result', '')

    # Mapeamento de resultados do chess.com
    DRAW_RESULTS = {'stalemate', 'insufficient', '50move', 'repetition',
                    'timevsinsufficient', 'agreed', 'bughousepartnerlose',
                    'threecheck', 'kingofthehill'}

    if my_result_raw == 'win':
        result = 'win'
    elif my_result_raw in DRAW_RESULTS:
        result = 'draw'
    else:
        result = 'loss'

    return jsonify({
        'ok': True,
        'result': result,
        'game_url': game.get('url', ''),
        'games_found': len(games_found),
    })


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
