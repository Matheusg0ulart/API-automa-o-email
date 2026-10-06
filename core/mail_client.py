import imaplib
import email
import email.message
from email.header import decode_header
from email.utils import parseaddr
import re
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("EmailAutomation")


def decode_mime_text(header_value: Optional[str]) -> str:
    """Decodifica cabeçalhos MIME com suporte a UTF-8, Latin-1 e outros encodings."""
    if not header_value:
        return ""
    try:
        decoded_fragments = decode_header(header_value)
        parts = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                enc = encoding or "utf-8"
                try:
                    parts.append(fragment.decode(enc, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    parts.append(fragment.decode("latin1", errors="replace"))
            else:
                parts.append(str(fragment))
        return "".join(parts).strip()
    except Exception as e:
        logger.debug(f"Falha ao decodificar header: {e}")
        return str(header_value)


def extract_text_from_message(msg: email.message.Message) -> str:
    """Extrai texto do corpo do e-mail, priorizando text/plain e limpando HTML se necessário."""
    text_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Ignora anexos
            if "attachment" in content_disposition:
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"

            if content_type == "text/plain":
                try:
                    decoded = payload.decode(charset, errors="replace")
                    text_parts.append(decoded)
                except (LookupError, UnicodeDecodeError):
                    text_parts.append(payload.decode("latin1", errors="replace"))

            elif content_type == "text/html":
                try:
                    decoded = payload.decode(charset, errors="replace")
                    html_parts.append(decoded)
                except (LookupError, UnicodeDecodeError):
                    html_parts.append(payload.decode("latin1", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
                text_parts.append(decoded)
            except (LookupError, UnicodeDecodeError):
                text_parts.append(payload.decode("latin1", errors="replace"))

    # Se encontramos texto puro, usamos ele
    if text_parts:
        return "\n".join(text_parts).strip()

    # Fallback: extrai texto de HTML removendo tags
    if html_parts:
        raw_html = "\n".join(html_parts)
        # Remove tags script e style
        cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags HTML comuns
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        # Converte entidades HTML básicas e normaliza espaços
        cleaned = re.sub(r"&nbsp;", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    return ""


class MailClient:
    """Cliente IMAP para conectar, listar, ler e mover e-mails com segurança."""

    def __init__(self, server: str, port: int, user: str, password: str):
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.connection: Optional[imaplib.IMAP4_SSL] = None
        self.supports_move = False

    def connect(self) -> bool:
        """Estabelece a conexão SSL com o servidor de e-mail e faz login."""
        try:
            logger.info(f"Conectando a {self.server}:{self.port}...")
            self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            self.connection.login(self.user, self.password)
            logger.info("Login realizado com sucesso.")

            # Verifica suporte à extensão MOVE (RFC 6855)
            typ, capabilities = self.connection.capability()
            if typ == "OK":
                caps = capabilities[0].decode("ascii", errors="ignore")
                self.supports_move = "MOVE" in caps
                logger.debug(f"Servidor suporta comando MOVE nativo: {self.supports_move}")

            return True
        except imaplib.IMAP4.error as e:
            logger.error(f"Erro de autenticação IMAP: {e}")
            raise
        except Exception as e:
            logger.error(f"Falha de conexão com o servidor de e-mail: {e}")
            raise

    def disconnect(self) -> None:
        """Encerra a conexão IMAP de forma segura."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None
            logger.info("Conexão IMAP encerrada.")

    def select_mailbox(self, mailbox_name: str = "INBOX") -> None:
        """Seleciona a pasta de trabalho (ex: INBOX)."""
        if not self.connection:
            raise ConnectionError("Cliente IMAP não está conectado.")
        status, _ = self.connection.select(f'"{mailbox_name}"')
        if status != "OK":
            raise ValueError(f"Não foi possível acessar a pasta: {mailbox_name}")

    def list_mailboxes(self) -> List[str]:
        """Retorna a lista de nomes de pastas existentes no servidor."""
        if not self.connection:
            raise ConnectionError("Cliente IMAP não está conectado.")
        status, folder_data = self.connection.list()
        folders = []
        if status == "OK":
            for item in folder_data:
                if isinstance(item, bytes):
                    item_str = item.decode("utf-8", errors="replace")
                    # Expressão regular para capturar o nome final da pasta
                    match = re.search(r'\"([^\"]+)\"$|([^\s\"]+)$', item_str)
                    if match:
                        folder_name = match.group(1) or match.group(2)
                        folders.append(folder_name)
        return folders

    def create_mailbox_if_not_exists(self, folder_name: str) -> None:
        """Cria uma nova pasta/label no servidor se ela ainda não existir."""
        if not self.connection:
            raise ConnectionError("Cliente IMAP não está conectado.")
        existing = self.list_mailboxes()
        # Normaliza comparação para não duplicar
        existing_normalized = [f.strip('"').lower() for f in existing]
        if folder_name.strip('"').lower() not in existing_normalized:
            logger.info(f"Criando pasta '{folder_name}' no servidor...")
            status, _ = self.connection.create(f'"{folder_name}"')
            if status != "OK":
                logger.warning(f"Aviso ao tentar criar pasta '{folder_name}'. Pode já existir ou ser restrita.")

    def search_emails(self, only_unread: bool = True, limit: int = 50) -> List[str]:
        """Busca e-mails na caixa postal selecionada retornando os UIDs em ordem decrescente (mais recentes primeiro)."""
        if not self.connection:
            raise ConnectionError("Cliente IMAP não está conectado.")

        criteria = "UNSEEN" if only_unread else "ALL"
        status, data = self.connection.uid("search", None, criteria)

        if status != "OK" or not data or not data[0]:
            return []

        # Lista de UIDs em bytes decodificados para string
        uids = data[0].split()
        uids_str = [uid.decode("ascii") for uid in uids]

        # Inverte para pegar os mais recentes primeiro
        uids_str.reverse()

        if limit > 0:
            return uids_str[:limit]
        return uids_str

    def fetch_email(self, uid: str) -> Optional[Dict]:
        """Obtém e faz parse completo de um e-mail pelo seu UID."""
        if not self.connection:
            raise ConnectionError("Cliente IMAP não está conectado.")

        status, data = self.connection.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data:
            logger.warning(f"Falha ao buscar e-mail UID {uid}")
            return None

        raw_email = None
        for response_part in data:
            if isinstance(response_part, tuple) and len(response_part) == 2:
                raw_email = response_part[1]
                break

        if not raw_email:
            return None

        msg = email.message_from_bytes(raw_email)

        # Assunto
        subject = decode_mime_text(msg.get("Subject", "(Sem Assunto)"))

        # Remetente (De)
        from_raw = decode_mime_text(msg.get("From", ""))
        sender_name, sender_email = parseaddr(from_raw)
        sender_email = sender_email.lower().strip()

        # Destinatário (Para)
        to_raw = decode_mime_text(msg.get("To", ""))

        # Data
        date_raw = decode_mime_text(msg.get("Date", ""))

        # Extrai o corpo do e-mail
        body_text = extract_text_from_message(msg)

        # Domínio do remetente
        sender_domain = ""
        if "@" in sender_email:
            sender_domain = sender_email.split("@")[-1].strip().lower()

        return {
            "uid": uid,
            "subject": subject,
            "sender_name": sender_name,
            "sender_email": sender_email,
            "sender_domain": sender_domain,
            "recipient": to_raw,
            "date": date_raw,
            "body": body_text,
            "snippet": (body_text[:120] + "...") if len(body_text) > 120 else body_text
        }

    def move_email(self, uid: str, destination_folder: str) -> bool:
        """Move o e-mail para a pasta de destino usando MOVE ou COPY+DELETE."""
        if not self.connection:
            raise ConnectionError("Cliente IMAP não está conectado.")

        try:
            self.create_mailbox_if_not_exists(destination_folder)

            if self.supports_move:
                res, _ = self.connection.uid("MOVE", uid, f'"{destination_folder}"')
                return res == "OK"
            else:
                # Fallback padrão IMAP: COPY -> FLAG DELETED -> EXPUNGE
                res_copy, _ = self.connection.uid("COPY", uid, f'"{destination_folder}"')
                if res_copy == "OK":
                    self.connection.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                    self.connection.expunge()
                    return True
                return False
        except Exception as e:
            logger.error(f"Erro ao mover e-mail UID {uid} para '{destination_folder}': {e}")
            return False

    def mark_as_read(self, uid: str) -> None:
        """Marca o e-mail como lido."""
        if self.connection:
            self.connection.uid("STORE", uid, "+FLAGS", "(\\Seen)")

    def mark_as_unread(self, uid: str) -> None:
        """Marca o e-mail como não lido."""
        if self.connection:
            self.connection.uid("STORE", uid, "-FLAGS", "(\\Seen)")
