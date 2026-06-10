// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(message, type) {
  type = type || 'info';
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const id = 'toast-' + Date.now();
  const icons = { success: 'check-circle-fill', danger: 'x-circle-fill',
                  warning: 'exclamation-triangle-fill', info: 'info-circle-fill' };
  container.insertAdjacentHTML('beforeend',
    '<div id="' + id + '" class="toast align-items-center text-bg-' + type + ' border-0 show mb-2" role="alert">' +
    '<div class="d-flex"><div class="toast-body">' +
    '<i class="bi bi-' + (icons[type] || icons.info) + ' me-2"></i>' + message +
    '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
    '</div></div>');
  setTimeout(function() { var el = document.getElementById(id); if (el) el.remove(); }, 4000);
}


// ── Flash auto-dismiss ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.flash-auto-dismiss').forEach(function(el) {
    setTimeout(function() {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      bsAlert.close();
    }, 5000);
  });

  // Format card selector
  document.querySelectorAll('.format-card-group').forEach(function(group) {
    group.querySelectorAll('.format-card').forEach(function(card) {
      card.addEventListener('click', function() {
        group.querySelectorAll('.format-card').forEach(function(c) { c.classList.remove('selected'); });
        card.classList.add('selected');
        var radio = card.querySelector('input[type="radio"]');
        if (radio) radio.checked = true;
      });
    });
  });
});


// ── Heartbeat / auto-refresh silencioso ──────────────────────────────────────

var _heartbeatTs = null;

function startHeartbeat(intervalMs) {
  intervalMs = intervalMs || 30000;

  fetch('/api/heartbeat')
    .then(function(r) { return r.json(); })
    .then(function(d) { _heartbeatTs = d.ts; })
    .catch(function() {});

  setInterval(function() {
    // Não recarrega se usuário está digitando
    var active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
    // Não recarrega se algum modal está aberto
    if (document.querySelector('.modal.show')) return;

    fetch('/api/heartbeat')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (_heartbeatTs !== null && d.ts > _heartbeatTs) {
          window.location.reload();
        }
      })
      .catch(function() {});
  }, intervalMs);
}


// ── Modal de Resultado ───────────────────────────────────────────────────────

var _rmMatchId = null;
var _rmP1Chess = null;
var _rmP2Chess = null;

function openResultModal(matchId, p1Name, p1Chess, p2Name, p2Chess, myReport) {
  _rmMatchId = matchId;
  _rmP1Chess = p1Chess;
  _rmP2Chess = p2Chess;

  _rmSetText('rm-p1-name', p1Name);
  _rmSetText('rm-p2-name', p2Name);
  _rmSetText('rm-p1-avatar', p1Name ? p1Name[0].toUpperCase() : '?');
  _rmSetText('rm-p2-avatar', p2Name ? p2Name[0].toUpperCase() : '?');

  _rmSetChessLink('rm-p1-chess', p1Chess);
  _rmSetChessLink('rm-p2-chess', p2Chess);

  var chessCheckEl = document.getElementById('rm-chess-check');
  if (chessCheckEl) chessCheckEl.classList.toggle('d-none', !(p1Chess && p2Chess));

  var statusEl = document.getElementById('rm-chess-status');
  if (statusEl) { statusEl.textContent = ''; statusEl.removeAttribute('style'); }

  document.querySelectorAll('input[name="rm-result"]').forEach(function(r) { r.checked = false; });
  var alreadyEl = document.getElementById('rm-already-reported');
  if (myReport && alreadyEl) {
    var labels = { win: 'Vitória', loss: 'Derrota', draw: 'Empate' };
    alreadyEl.textContent = 'Você já informou: ' + (labels[myReport] || myReport) + '. Pode alterar abaixo.';
    alreadyEl.classList.remove('d-none');
    var radio = document.querySelector('input[name="rm-result"][value="' + myReport + '"]');
    if (radio) radio.checked = true;
  } else if (alreadyEl) {
    alreadyEl.classList.add('d-none');
  }

  var detailLink = document.getElementById('rm-detail-link');
  if (detailLink) detailLink.href = '/match/' + matchId;

  bootstrap.Modal.getOrCreateInstance(document.getElementById('resultModal')).show();
}

function _rmSetText(id, text) {
  var el = document.getElementById(id);
  if (el) el.textContent = text || '';
}

function _rmSetChessLink(id, chessUser) {
  var el = document.getElementById(id);
  if (!el) return;
  if (chessUser) {
    el.href = 'https://www.chess.com/member/' + chessUser;
    el.textContent = '@' + chessUser;
    el.classList.remove('d-none');
  } else {
    el.classList.add('d-none');
  }
}

function submitResult() {
  var result = document.querySelector('input[name="rm-result"]:checked');
  if (!result) { showToast('Selecione um resultado.', 'warning'); return; }
  result = result.value;

  var btn = document.getElementById('rm-submit');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Enviando…';

  fetch('/match/' + _rmMatchId + '/submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: 'result=' + result,
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.ok) {
      bootstrap.Modal.getOrCreateInstance(document.getElementById('resultModal')).hide();
      showToast(data.message || 'Resultado registrado!', 'success');
      setTimeout(function() { window.location.reload(); }, 900);
    } else {
      showToast(data.error || 'Erro ao registrar resultado.', 'danger');
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Confirmar';
    }
  })
  .catch(function() {
    showToast('Erro de conexão.', 'danger');
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Confirmar';
  });
}

function checkChessResult() {
  var statusEl = document.getElementById('rm-chess-status');
  var btn = document.getElementById('rm-chess-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Consultando…'; }
  if (statusEl) { statusEl.textContent = ''; statusEl.removeAttribute('style'); }

  fetch('/match/' + _rmMatchId + '/check-result')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        var labels = { win: '🏆 Vitória', draw: '〰 Empate', loss: '❌ Derrota' };
        var radio = document.querySelector('input[name="rm-result"][value="' + data.result + '"]');
        if (radio) radio.checked = true;
        if (statusEl) {
          var extra = data.games_found > 1 ? ' (' + data.games_found + ' jogos, mais recente usado)' : '';
          statusEl.textContent = 'Encontrado: ' + (labels[data.result] || data.result) + extra;
          statusEl.style.color = 'var(--success)';
        }
      } else {
        if (statusEl) { statusEl.textContent = data.error; statusEl.style.color = 'var(--error)'; }
      }
    })
    .catch(function() {
      if (statusEl) statusEl.textContent = 'Erro ao consultar o chess.com.';
    })
    .finally(function() {
      if (btn) { btn.disabled = false; btn.innerHTML = '<img src="https://www.chess.com/favicon.ico" width="14" class="me-1">Verificar no chess.com'; }
    });
}


// ── Rating chess.com (lazy-load) ──────────────────────────────────────────────

function loadChessRatings() {
  document.querySelectorAll('[data-chess-user]').forEach(function(el) {
    var username = el.dataset.chessUser;
    if (!username) return;
    fetch('/api/chess-rating/' + encodeURIComponent(username))
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!d.ok || !d.ratings) return;
        var r = d.ratings;
        var parts = [];
        if (r.rapid)  parts.push('⚡' + r.rapid);
        if (r.blitz)  parts.push('🔥' + r.blitz);
        if (r.bullet) parts.push('💨' + r.bullet);
        if (parts.length) el.textContent = parts.join(' · ');
      })
      .catch(function() {});
  });
}


// ── Chat (polling) ────────────────────────────────────────────────────────────

function initChat(matchId, canSend) {
  var box     = document.getElementById('chatBox');
  var emptyEl = document.getElementById('chatEmpty');
  var form    = document.getElementById('chatForm');
  var input   = document.getElementById('chatInput');
  if (!box) return;

  var lastId = 0;

  function renderMessages(msgs) {
    msgs.forEach(function(m) {
      if (emptyEl) emptyEl.style.display = 'none';
      var div = document.createElement('div');
      div.className = 'chat-bubble ' + (m.mine ? 'mine' : 'theirs');
      div.innerHTML =
        '<div class="chat-meta">' + (m.mine ? 'Você' : m.user) + ' · ' + m.ts + '</div>' +
        '<div class="chat-text">' + m.text.replace(/</g, '&lt;') + '</div>';
      box.appendChild(div);
      lastId = Math.max(lastId, m.id);
    });
    if (msgs.length) box.scrollTop = box.scrollHeight;
  }

  function poll() {
    fetch('/match/' + matchId + '/messages?after=' + lastId)
      .then(function(r) { return r.json(); })
      .then(function(d) { renderMessages(d.messages || []); })
      .catch(function() {});
  }

  poll();
  setInterval(poll, 15000);

  if (canSend && form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      var text = input.value.trim();
      if (!text) return;
      input.value = '';
      fetch('/match/' + matchId + '/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'message=' + encodeURIComponent(text),
      })
      .then(function() { poll(); })
      .catch(function() {});
    });
  }
}
