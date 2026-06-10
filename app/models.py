from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True, nullable=True)
    chess_username = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='player')  # admin | player
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def display_name(self):
        return self.name or self.username

    participations = db.relationship('Participant', backref='user', lazy='dynamic',
                                     foreign_keys='Participant.user_id')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Championship(db.Model):
    __tablename__ = 'championships'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    format = db.Column(db.String(20), nullable=False)  # elimination | round_robin
    status = db.Column(db.String(20), default='draft')  # draft | active | finished
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    block_on_inconsistency = db.Column(db.Boolean, default=True)
    current_round = db.Column(db.Integer, default=1)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    creator = db.relationship('User', foreign_keys=[created_by], backref='created_championships')
    winner = db.relationship('User', foreign_keys=[winner_id])
    participants = db.relationship('Participant', backref='championship', lazy='dynamic')
    matches = db.relationship('Match', backref='championship', lazy='dynamic')

    def get_active_participants(self):
        return self.participants.filter_by(is_disqualified=False).all()

    def has_inconsistencies(self):
        return self.matches.filter_by(status='inconsistent').count() > 0

    def get_standings(self):
        standings = []
        for p in self.get_active_participants():
            stats = self._player_stats(p.user_id)
            standings.append({'user': p.user, 'participant': p, **stats})
        standings.sort(key=lambda x: (-x['points'], -x['wins'], -x['draws']))
        return standings

    def _player_stats(self, user_id):
        wins = draws = losses = 0
        completed = Match.query.filter(
            Match.championship_id == self.id,
            Match.status == 'completed',
            db.or_(Match.player1_id == user_id, Match.player2_id == user_id)
        ).all()
        for m in completed:
            if m.final_result == 'draw':
                draws += 1
            elif (m.final_result == 'player1_win' and m.player1_id == user_id) or \
                 (m.final_result == 'player2_win' and m.player2_id == user_id):
                wins += 1
            else:
                losses += 1
        return {
            'wins': wins, 'draws': draws, 'losses': losses,
            'points': wins * 3 + draws,
            'played': wins + draws + losses,
        }

    def __repr__(self):
        return f'<Championship {self.name}>'


class Participant(db.Model):
    __tablename__ = 'participants'

    id = db.Column(db.Integer, primary_key=True)
    championship_id = db.Column(db.Integer, db.ForeignKey('championships.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_disqualified = db.Column(db.Boolean, default=False)
    disqualified_at = db.Column(db.DateTime)
    disqualification_reason = db.Column(db.String(500))
    seed = db.Column(db.Integer)

    __table_args__ = (db.UniqueConstraint('championship_id', 'user_id'),)

    def __repr__(self):
        return f'<Participant u={self.user_id} c={self.championship_id}>'


class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column(db.Integer, primary_key=True)
    championship_id = db.Column(db.Integer, db.ForeignKey('championships.id'), nullable=False)
    player1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    player2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    round = db.Column(db.Integer, nullable=False, default=1)
    bracket_position = db.Column(db.Integer, default=0)

    # pending | awaiting_confirmation | completed | inconsistent | bye | wo
    status = db.Column(db.String(30), default='pending')

    player1_reported = db.Column(db.String(10))  # win | loss | draw
    player2_reported = db.Column(db.String(10))  # win | loss | draw

    # player1_win | player2_win | draw
    final_result = db.Column(db.String(20))

    is_bye = db.Column(db.Boolean, default=False)
    invite_link = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    messages = db.relationship('MatchMessage', backref='match', lazy='dynamic',
                               order_by='MatchMessage.created_at')

    player1 = db.relationship('User', foreign_keys=[player1_id], backref='matches_as_p1')
    player2 = db.relationship('User', foreign_keys=[player2_id], backref='matches_as_p2')

    def get_winner_id(self):
        if self.final_result == 'player1_win':
            return self.player1_id
        if self.final_result == 'player2_win':
            return self.player2_id
        return None

    def get_winner(self):
        wid = self.get_winner_id()
        if wid:
            return User.query.get(wid)
        return None

    def player_result_label(self, user_id):
        if self.final_result == 'draw':
            return 'Empate'
        w = self.get_winner_id()
        if w == user_id:
            return 'Vitória'
        return 'Derrota'

    def submit_result(self, user_id, reported):
        """reported: 'win' | 'loss' | 'draw'"""
        if self.status in ('completed', 'bye', 'wo'):
            return False, 'Partida já encerrada.'
        if self.player1_id == user_id:
            self.player1_reported = reported
        elif self.player2_id == user_id:
            self.player2_reported = reported
        else:
            return False, 'Você não é participante desta partida.'
        self._validate()
        return True, 'Resultado registrado.'

    def _validate(self):
        p1 = self.player1_reported
        p2 = self.player2_reported
        if p1 and p2:
            if (p1 == 'win' and p2 == 'loss') or \
               (p1 == 'loss' and p2 == 'win') or \
               (p1 == 'draw' and p2 == 'draw'):
                self.final_result = 'player1_win' if p1 == 'win' else (
                    'player2_win' if p1 == 'loss' else 'draw')
                self.status = 'completed'
                self.completed_at = datetime.utcnow()
            else:
                self.status = 'inconsistent'
        elif p1 or p2:
            self.status = 'awaiting_confirmation'

    def force_result(self, result):
        """Admin override: result = 'player1_win' | 'player2_win' | 'draw'"""
        self.final_result = result
        self.status = 'completed'
        self.completed_at = datetime.utcnow()

    def apply_wo(self, disqualified_user_id):
        """W.O. when a player is disqualified."""
        if self.player1_id == disqualified_user_id:
            self.final_result = 'player2_win'
        else:
            self.final_result = 'player1_win'
        self.status = 'wo'
        self.completed_at = datetime.utcnow()

    def __repr__(self):
        return f'<Match {self.id} R{self.round}>'


class MatchMessage(db.Model):
    __tablename__ = 'match_messages'

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[user_id])

    def to_dict(self, viewer_id):
        return {
            'id': self.id,
            'user': self.author.display_name,
            'text': self.message,
            'mine': self.user_id == viewer_id,
            'ts': self.created_at.strftime('%d/%m %H:%M'),
        }

    def __repr__(self):
        return f'<MatchMessage {self.id}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def detail(self):
        """Alias para compatibilidade com templates."""
        return self.details

    @property
    def created_at(self):
        """Alias para compatibilidade com templates."""
        return self.timestamp

    def __repr__(self):
        return f'<AuditLog {self.action}>'
