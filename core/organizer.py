import logging
from typing import List, Dict, Any, Optional
from core.mail_client import MailClient
from core.classifier import EmailClassifier
from core.reporter import EmailReporter
from core.ai_analyzer import AIAnalyzer
from core.auto_reply import AutoResponder
from core.database import Database
from config import settings

logger = logging.getLogger("EmailAutomation")


class EmailOrganizer:
    """Orquestrador do fluxo completo de leitura, classificação por IA, resposta e relatórios."""

    def __init__(self, dry_run: Optional[bool] = None):
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.rules = settings.load_rules()
        self.classifier = EmailClassifier(self.rules, company_domain=settings.COMPANY_DOMAIN)
        self.reporter = EmailReporter(settings.REPORTS_DIR)
        self.db = Database()
        self.ai = AIAnalyzer(
            gemini_api_key=settings.GEMINI_API_KEY,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.auto_responder = AutoResponder(
            smtp_server=settings.SMTP_SERVER,
            smtp_port=settings.SMTP_PORT,
            user=settings.EMAIL_USER,
            password=settings.EMAIL_PASSWORD,
            enabled=settings.ENABLE_AUTO_REPLY
        )
        self.client = MailClient(
            server=settings.IMAP_SERVER,
            port=settings.IMAP_PORT,
            user=settings.EMAIL_USER,
            password=settings.EMAIL_PASSWORD
        )

    def process_emails(self, limit: Optional[int] = None, only_unread: Optional[bool] = None) -> Dict[str, Any]:
        """
        Executa a varredura e triagem dos e-mails da caixa postal configurada.
        """
        fetch_limit = limit if limit is not None else settings.MAX_EMAILS_PER_RUN
        fetch_unread = only_unread if only_unread is not None else settings.ONLY_UNREAD

        processed_items: List[Dict[str, Any]] = []

        logger.info(f"Iniciando processamento (Modo Simulação: {self.dry_run})...")
        self.client.connect()

        try:
            self.client.select_mailbox(settings.MAILBOX_SOURCE)
            uids = self.client.search_emails(only_unread=fetch_unread, limit=fetch_limit)
            logger.info(f"Total de e-mails encontrados para processamento: {len(uids)}")

            for index, uid in enumerate(uids, start=1):
                email_data = self.client.fetch_email(uid)
                if not email_data:
                    continue

                # 1. Classificação por Regras e Heurísticas
                classification = self.classifier.classify(email_data)
                target_folder = classification["target_folder"]
                category_name = classification["category_name"]
                category_id = classification["category_id"]
                score = classification["score"]
                reasons = classification["reasons"]

                # 2. Análise Inteligente de IA (Resumo, Urgência, Valor Estimado)
                ai_insights = self.ai.analyze(email_data)
                summary = ai_insights.get("summary", "")
                urgency = ai_insights.get("urgency", "Média")
                estimated_value = ai_insights.get("estimated_value", "Não informado")

                # 3. Resposta Automática Comercial (se habilitado)
                replied = False
                if self.auto_responder.should_reply(email_data, category_id):
                    # Não responde se já foi respondido anteriormente
                    if not self.db.is_replied(uid):
                        replied = self.auto_responder.send_commercial_reply(email_data, dry_run=self.dry_run)

                # 4. Ação no Servidor (Mover ou Simular)
                status_action = ""
                if self.dry_run:
                    status_action = f"[SIMULAÇÃO] Direcionaria para: {target_folder}"
                else:
                    moved = self.client.move_email(uid, target_folder)
                    if moved:
                        status_action = f"Movido com sucesso para '{target_folder}'"
                    else:
                        status_action = f"Falha ao mover para '{target_folder}'"

                record = {
                    "uid": uid,
                    "date": email_data["date"],
                    "sender_name": email_data["sender_name"],
                    "sender_email": email_data["sender_email"],
                    "sender_domain": email_data["sender_domain"],
                    "subject": email_data["subject"],
                    "category_id": category_id,
                    "category_name": category_name,
                    "target_folder": target_folder,
                    "score": score,
                    "reasons": reasons,
                    "summary": summary,
                    "urgency": urgency,
                    "estimated_value": estimated_value,
                    "auto_replied": replied,
                    "is_dry_run": self.dry_run,
                    "status": status_action,
                    "snippet": email_data["snippet"]
                }

                # Salva no banco de dados SQLite para histórico e Dashboard
                self.db.save_email(record)
                processed_items.append(record)

                logger.info(
                    f"[{index}/{len(uids)}] '{email_data['subject'][:30]}' -> "
                    f"{category_name} | Urgência: {urgency} | Valor: {estimated_value} | {status_action}"
                )

        finally:
            self.client.disconnect()

        # Gera os relatórios se houver e-mails analisados
        report_result = None
        if processed_items:
            report_result = self.reporter.generate_report(processed_items, dry_run=self.dry_run)

        return {
            "processed_count": len(processed_items),
            "dry_run": self.dry_run,
            "items": processed_items,
            "report": report_result
        }
