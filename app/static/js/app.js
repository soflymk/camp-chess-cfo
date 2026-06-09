/* CFO Chess – app.js */

// ── Toast helper ──────────────────────────────────────────────────────────
window.showToast = function(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const icons = { success: '✅', danger: '❌', warning: '⚠️', info: 'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast align-items-center border-0 text-white`;
  el.style.background = type === 'success' ? '#16a34a'
    : type === 'danger' ? '#dc2626'
    : type === 'warning' ? '#ca8a04' : '#0284c7';
  el.setAttribute('role', 'alert');
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body fw-medium">${icons[type] || ''} ${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(el);
  const t = new bootstrap.Toast(el, { delay: 4000 });
  t.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
};

// ── Auto-dismiss flash alerts ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash-auto-dismiss').forEach(el => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });
});

// ── Format card selector ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.format-card').forEach(card => {
    card.addEventListener('click', () => {
      const group = card.closest('.format-card-group');
      if (group) group.querySelectorAll('.format-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      const radio = card.querySelector('input[type=radio]');
      if (radio) radio.checked = true;
    });
  });
});

// ── Chat ──────────────────────────────────────────────────────────────────
window.initChat = function(matchId, isActive) {
  const box    = document.getElementById('chatBox');
  const form   = document.getElementById('chatForm');
  const input  = document.getElementById('chatInput');
  const empty  = document.getElementById('chatEmpty');
  if (!box) return;

  let lastId = 0;
  let polling = null;

  function scrollBottom() {
    box.scrollTop = box.scrollHeight;
  }

  function renderMessage(msg) {
    const wrap = document.createElement('div');
    wrap.style.display = 'flex';
    wrap.style.flexDirection = 'column';
    wrap.style.alignItems = msg.mine ? 'flex-end' : 'flex-start';

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${msg.mine ? 'chat-bubble-mine' : 'chat-bubble-other'}`;
    bubble.textContent = msg.text;

    const meta = document.createElement('div');
    meta.className = `chat-meta ${msg.mine ? 'chat-meta-mine' : ''}`;
    meta.textContent = msg.mine ? msg.ts : `${msg.user} · ${msg.ts}`;

    wrap.appendChild(bubble);
    wrap.appendChild(meta);
    return wrap;
  }

  async function fetchMessages() {
    try {
      const res = await fetch(`/match/${matchId}/messages?after=${lastId}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.messages.length > 0) {
        if (empty) empty.style.display = 'none';
        data.messages.forEach(msg => {
          box.appendChild(renderMessage(msg));
          lastId = Math.max(lastId, msg.id);
        });
        scrollBottom();
      } else if (lastId === 0 && empty) {
        empty.style.display = 'flex';
      }
    } catch (e) { /* silencioso */ }
  }

  // Carga inicial + polling
  fetchMessages();
  if (isActive) {
    polling = setInterval(fetchMessages, 15000);
  }

  // Parar polling quando tab não estiver ativa
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { clearInterval(polling); polling = null; }
    else if (isActive) { polling = setInterval(fetchMessages, 15000); }
  });

  // Submit via fetch
  if (form && isActive) {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      try {
        const fd = new FormData();
        fd.append('message', text);
        const res = await fetch(`/match/${matchId}/message`, { method: 'POST', body: fd });
        const data = await res.json();
        if (data.ok) {
          input.value = '';
          await fetchMessages();
        } else {
          showToast(data.error || 'Erro ao enviar.', 'danger');
        }
      } catch (e) {
        showToast('Erro de conexão.', 'danger');
      } finally {
        btn.disabled = false;
        input.focus();
      }
    });
  }
};
