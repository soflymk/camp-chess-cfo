# ♟ CFO Chess — Sistema de Campeonatos de Xadrez

Sistema web completo para gerenciamento de campeonatos de xadrez com suporte a **Eliminatório** (bracket) e **Pontos Corridos** (todos contra todos).

---

## Funcionalidades

- **Autenticação** — cadastro, login/logout, perfis Admin e Jogador
- **Eliminatório** — bracket automático com suporte a BYE
- **Pontos Corridos** — geração automática de confrontos, tabela de classificação (V=3, E=1, D=0)
- **Sistema de partidas** — ambos os jogadores registram resultado; validação cruzada; detecção de inconsistência
- **Dashboard Admin** — visão geral, alertas de inconsistência, log de auditoria
- **Dashboard Jogador** — partidas pendentes, histórico, links para registrar resultado
- **Desclassificação** — W.O. automático nas partidas pendentes do jogador desclassificado
- **Resolução admin** — administrador pode definir resultado de partidas inconsistentes
- **Reset** — campeonato pode ser resetado para rascunho

---

## Rodando localmente

### Pré-requisitos

- Python 3.11+
- pip

### Instalação

```bash
# Clone ou baixe o projeto
cd CFO-chess

# Crie e ative o ambiente virtual
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### Configuração

Copie `.env.example` para `.env` e ajuste:

```bash
cp .env.example .env
```

Edite `.env`:
```
FLASK_ENV=development
SECRET_KEY=sua-chave-secreta-aqui
```

### Inicializar banco e migrations

```bash
# Inicializar migrations (primeira vez)
flask db init
flask db migrate -m "initial"
flask db upgrade

# OU simplesmente rodar (cria tabelas automaticamente)
python run.py
```

### Executar

```bash
python run.py
```

Acesse: http://localhost:5000

### Criar primeiro usuário Admin

Após cadastrar o primeiro usuário normalmente, acesse o shell Flask para promovê-lo:

```bash
flask shell
```
```python
from app.models import User
from app import db
u = User.query.filter_by(username='seu_usuario').first()
u.role = 'admin'
db.session.commit()
```

---

## Deploy no Render

### Passo a passo

1. **Faça push** do projeto para um repositório GitHub (ou GitLab)

2. **Acesse** [render.com](https://render.com) e crie uma conta

3. **New → Web Service** → conecte seu repositório

4. **Configure o serviço:**

   | Campo | Valor |
   |---|---|
   | Environment | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn run:app` |

5. **Adicione as variáveis de ambiente** em *Environment → Add Environment Variable*:

   | Variável | Valor |
   |---|---|
   | `SECRET_KEY` | gere uma chave forte (ex: `python -c "import secrets; print(secrets.token_hex(32))"`) |
   | `FLASK_ENV` | `production` |
   | `DATABASE_URL` | *(deixar vazio para SQLite, ou adicionar URL do PostgreSQL)* |

6. **Clique em Create Web Service**. O Render fará o build e deploy automático.

### Usando PostgreSQL no Render (opcional)

1. No Render, crie um **New → PostgreSQL**
2. Copie a **Internal Database URL**
3. Adicione como variável de ambiente `DATABASE_URL` no seu Web Service
4. O app ajusta automaticamente `postgres://` → `postgresql://`

### Migrations em produção

No Render, adicione ao **Build Command**:
```
pip install -r requirements.txt && flask db upgrade
```

Ou, se não usar Flask-Migrate, o `db.create_all()` no `app/__init__.py` cria as tabelas automaticamente no primeiro start.

---

## Estrutura do projeto

```
CFO-chess/
├── app/
│   ├── __init__.py          # factory, extensões
│   ├── models.py            # User, Championship, Participant, Match, AuditLog
│   ├── services.py          # lógica de negócio (bracket, round robin, DQ, auditoria)
│   ├── routes/
│   │   ├── auth.py          # login, logout, register
│   │   ├── admin.py         # dashboard admin, CRUD campeonatos, users
│   │   ├── player.py        # dashboard jogador
│   │   ├── championship.py  # bracket view, standings view
│   │   └── match.py         # detalhe partida, submit resultado
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── admin/
│   │   ├── player/
│   │   ├── championship/
│   │   └── match/
│   └── static/css/main.css
├── config.py
├── run.py
├── requirements.txt
├── Procfile
├── runtime.txt
└── README.md
```

---

## Stack

- **Backend:** Python 3.11 + Flask 3
- **ORM:** SQLAlchemy + Flask-SQLAlchemy
- **Auth:** Flask-Login
- **Migrations:** Flask-Migrate (Alembic)
- **Frontend:** Bootstrap 5 + Jinja2
- **Servidor:** Gunicorn
- **Banco:** SQLite (dev) / PostgreSQL (produção)
