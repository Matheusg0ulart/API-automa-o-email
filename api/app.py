from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from core.database import Database
from core.organizer import EmailOrganizer
from core.classifier import EmailClassifier
from core.ai_analyzer import AIAnalyzer

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_HTML = BASE_DIR / "web" / "dashboard.html"

app = FastAPI(
    title="AutoMail AI - Automação Comercial & Corporativa",
    description="API REST e Painel para Triagem, Classificação por IA e Resposta Automática de E-mails.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()
rules = settings.load_rules()
classifier = EmailClassifier(rules, company_domain=settings.COMPANY_DOMAIN)
ai_analyzer = AIAnalyzer(
    gemini_api_key=settings.GEMINI_API_KEY,
    openai_api_key=settings.OPENAI_API_KEY
)


class ClassifyRequest(BaseModel):
    subject: str = ""
    body: str = ""
    sender_name: Optional[str] = ""
    sender_email: Optional[str] = ""


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    """Serve a interface gráfica do Dashboard no navegador."""
    if not DASHBOARD_HTML.exists():
        raise HTTPException(status_code=404, detail="Arquivo dashboard.html não encontrado.")
    with open(DASHBOARD_HTML, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/dashboard-data", tags=["Dashboard"])
def get_dashboard_data():
    """Retorna métricas consolidadas e e-mails recentes para o Dashboard."""
    metrics = db.get_metrics()
    recent = db.get_recent(limit=50)
    return {
        "metrics": metrics,
        "recent_emails": recent,
        "config": {
            "email_user": settings.EMAIL_USER,
            "imap_server": settings.IMAP_SERVER,
            "auto_reply_enabled": settings.ENABLE_AUTO_REPLY,
            "ai_active": bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)
        }
    }


@app.post("/api/processar", tags=["Operações"])
def trigger_processing(
    dry_run: bool = Query(True, description="True para simulação sem mover, False para mover"),
    limit: int = Query(20, description="Quantidade máxima de e-mails para processar")
):
    """
    Dispara a triagem e processamento dos e-mails sob demanda.
    Pode ser invocado por CRONs, webhooks de ERPs ou pelo botão do Dashboard.
    """
    if not settings.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Credenciais de e-mail não configuradas no arquivo .env!"
        )

    try:
        organizer = EmailOrganizer(dry_run=dry_run)
        result = organizer.process_emails(limit=limit, only_unread=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/classificar-texto", tags=["Inteligência Artificial"])
def classify_text(req: ClassifyRequest):
    """
    Classifica um texto ou assunto em tempo real usando regras heurísticas e IA.
    Retorna categoria, pontuação, urgência, valor estimado e resumo.
    """
    email_data = {
        "subject": req.subject,
        "body": req.body,
        "sender_name": req.sender_name or "",
        "sender_email": req.sender_email or "",
        "sender_domain": req.sender_email.split("@")[-1] if "@" in (req.sender_email or "") else "",
        "snippet": req.body[:500]
    }

    classification = classifier.classify(email_data)
    ai_insights = ai_analyzer.analyze(email_data)

    return {
        "category_id": classification["category_id"],
        "category_name": classification["category_name"],
        "target_folder": classification["target_folder"],
        "score": classification["score"],
        "reasons": classification["reasons"],
        "ai_insights": ai_insights
    }


@app.get("/api/relatorios", tags=["Relatórios"])
def list_reports():
    """Lista todos os relatórios Excel gerados."""
    reports = []
    for f in sorted(settings.REPORTS_DIR.glob("*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True):
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        reports.append({
            "filename": f.name,
            "created_at": mtime,
            "size_kb": round(f.stat().st_size / 1024, 2)
        })
    return reports


@app.get("/api/relatorios/download/{filename}", tags=["Relatórios"])
def download_report(filename: str):
    """Baixa um relatório Excel ou CSV diretamente pelo navegador."""
    file_path = settings.REPORTS_DIR / filename
    if not file_path.exists() or file_path.parent != settings.REPORTS_DIR:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if filename.endswith(".xlsx") else "text/csv"
    return FileResponse(file_path, media_type=media_type, filename=filename)


@app.get("/api/status", tags=["Sistema"])
def get_system_status():
    """Retorna o estado operacional da automação e seus módulos."""
    return {
        "status": "online",
        "configured": settings.is_configured(),
        "email_user": settings.EMAIL_USER if settings.is_configured() else "Não configurado",
        "imap_server": settings.IMAP_SERVER,
        "auto_reply_enabled": settings.ENABLE_AUTO_REPLY,
        "ai_provider": "Gemini" if settings.GEMINI_API_KEY else ("OpenAI" if settings.OPENAI_API_KEY else "Heurística Local (Offline)")
    }
