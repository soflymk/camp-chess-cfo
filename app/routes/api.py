"""API endpoints: heartbeat (auto-refresh) e integração chess.com."""
import json
import urllib.request
from datetime import datetime
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from ..models import Match, Participant
from sqlalchemy import or_

api_bp = Blueprint('api', __name__)

_CHESS_UA = 'CFO-Chess-App/1.0'


# ---------------------------------------------------------------------------
# Heartbeat — usado pelo frontend para detectar novidades e recarregar
# ---------------------------------------------------------------------------

@api_bp.route('/heartbeat')
@login_required
def heartbeat():
    """Retorna o timestamp da última alteração em partidas relevantes."""
    if current_user.is_admin:
        matches = Match.query.filter(Match.status != 'bye').all()
    else:
        part_ids = [p.championship_id for p in
                    Participant.query.filter_by(user_id=current_user.id).all()]
        if not part_ids:
            return jsonify({'ts': 0})
        matches = Match.query.filter(Match.championship_id.in_(part_ids)).all()

    ts = 0
    for m in matches:
        for dt in (m.completed_at, m.created_at):
            if dt:
                t = int(dt.timestamp())
                if t > ts:
                    ts = t

    return jsonify({'ts': ts})


# ---------------------------------------------------------------------------
# Rating chess.com
# ---------------------------------------------------------------------------

@api_bp.route('/chess-rating/<username>')
def chess_rating(username):
    """Busca rating público de um jogador no chess.com."""
    url = f'https://api.chess.com/pub/player/{username}/stats'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': _CHESS_UA})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        ratings = {}
        for mode in ('chess_rapid', 'chess_blitz', 'chess_bullet'):
            if mode in data and 'last' in data[mode]:
                ratings[mode.replace('chess_', '')] = data[mode]['last']['rating']

        return jsonify({'ok': True, 'ratings': ratings})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return jsonify({'ok': False, 'error': 'Usuário não encontrado no chess.com'})
        return jsonify({'ok': False, 'error': f'Erro HTTP {e.code}'})
    except Exception as e:
        return jsonify({'ok': False, 'error': 'Não foi possível consultar o chess.com'})
