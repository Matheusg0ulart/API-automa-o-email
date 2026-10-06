import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Diretório raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variáveis do arquivo .env
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

# Configurações de Conexão IMAP
EMAIL_USER = os.getenv("EMAIL_USER", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com").strip()
IMAP_PORT = int(os.getenv("IMAP_PORT", "993").strip() or 993)

# Parâmetros de Execução
MAILBOX_SOURCE = os.getenv("MAILBOX_SOURCE", "INBOX").strip()
ONLY_UNREAD = os.getenv("ONLY_UNREAD", "True").strip().lower() in ("true", "1", "yes", "sim")
MAX_EMAILS_PER_RUN = int(os.getenv("MAX_EMAILS_PER_RUN", "50").strip() or 50)
DRY_RUN = os.getenv("DRY_RUN", "True").strip().lower() in ("true", "1", "yes", "sim")
COMPANY_DOMAIN = os.getenv("COMPANY_DOMAIN", "").strip().lower()
MONITOR_INTERVAL_MINUTES = int(os.getenv("MONITOR_INTERVAL_MINUTES", "5").strip() or 5)

# Inteligência Artificial (Opcional - Gemini ou OpenAI)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# Resposta Automática (Auto-Reply)
ENABLE_AUTO_REPLY = os.getenv("ENABLE_AUTO_REPLY", "False").strip().lower() in ("true", "1", "yes", "sim")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com" if "gmail" in IMAP_SERVER.lower() else "mail.seudominio.com.br").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587").strip() or 587)

# Servidor Web & Dashboard
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1").strip()
WEB_PORT = int(os.getenv("WEB_PORT", "8000").strip() or 8000)

# Diretórios de Saída
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "relatorios"
CONFIG_DIR = BASE_DIR / "config"
RULES_FILE = CONFIG_DIR / "rules.json"

LOGS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


def is_configured() -> bool:
    """Verifica se as credenciais mínimas foram preenchidas no .env."""
    return bool(EMAIL_USER and EMAIL_PASSWORD and EMAIL_PASSWORD != "sua_senha_de_app_ou_senha_corporativa")


def load_rules() -> dict:
    """Carrega as regras de classificação do arquivo rules.json."""
    if not RULES_FILE.exists():
        raise FileNotFoundError(f"Arquivo de regras não encontrado: {RULES_FILE}")
    
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rules(rules: dict) -> None:
    """Salva as regras atualizadas no arquivo rules.json."""
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
