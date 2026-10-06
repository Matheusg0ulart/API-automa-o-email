import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

logger = logging.getLogger("EmailAutomation")


class AutoResponder:
    """Gerencia o envio de respostas automáticas seguras e personalizadas para leads comerciais."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        user: str,
        password: str,
        enabled: bool = False
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.user = user
        self.password = password
        self.enabled = enabled

    def should_reply(self, email_data: Dict[str, Any], category_id: str) -> bool:
        """Verifica se o e-mail qualifica para receber auto-resposta."""
        if not self.enabled:
            return False

        # Apenas para comercial
        if category_id != "comercial":
            return False

        sender_email = email_data.get("sender_email", "").lower()

        # Evita responder robôs, newsletters ou a própria conta
        ignore_patterns = ["no-reply", "noreply", "mailer-daemon", "bounce", "postmaster", self.user.lower()]
        if any(pat in sender_email for pat in ignore_patterns):
            return False

        return True

    def send_commercial_reply(self, email_data: Dict[str, Any], dry_run: bool = True) -> bool:
        """Envia a confirmação de recebimento para o lead ou simula o envio."""
        sender_email = email_data.get("sender_email", "")
        sender_name = email_data.get("sender_name", "") or "Cliente"
        subject = email_data.get("subject", "")

        if dry_run:
            logger.info(f"[SIMULAÇÃO AUTO-REPLY] Resposta automática comercial seria enviada para: {sender_email}")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"Equipe Comercial <{self.user}>"
            msg["To"] = sender_email
            msg["Subject"] = f"Recebemos sua solicitação: {subject}"

            text_content = f"""Olá {sender_name},

Confirmamos o recebimento da sua solicitação de orçamento/proposta referente a:
"{subject}".

Nossa equipe comercial já foi notificada e está analisando os detalhes para lhe retornar com a melhor proposta no menor prazo possível.

Se houver alguma urgência ou informação adicional, fique à vontade para responder a esta mensagem.

Atenciosamente,
Equipe Comercial
"""

            html_content = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                <h2 style="color: #1F4E79; margin-top: 0;">Recebemos sua mensagem!</h2>
                <p>Olá <strong>{sender_name}</strong>,</p>
                <p>Agradecemos pelo seu contato de interesse comercial.</p>
                <div style="background-color: #F4F7FB; border-left: 4px solid #1F4E79; padding: 12px; margin: 15px 0;">
                    <p style="margin: 0; font-size: 14px; color: #555;"><strong>Assunto:</strong> {subject}</p>
                </div>
                <p>Nossa equipe comercial já foi notificada e estamos preparando um retorno personalizado para atender às suas necessidades com prioridade.</p>
                <br>
                <p style="font-size: 13px; color: #777;">Atenciosamente,<br><strong>Equipe Comercial</strong></p>
            </div>
            """

            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            logger.info(f"Conectando ao SMTP {self.smtp_server}:{self.smtp_port} para auto-resposta...")
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10) as server:
                    server.login(self.user, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(self.user, self.password)
                    server.send_message(msg)

            logger.info(f"Auto-resposta enviada com sucesso para: {sender_email}")
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar auto-resposta comercial para {sender_email}: {e}")
            return False
