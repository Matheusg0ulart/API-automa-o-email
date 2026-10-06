import sys
from colorama import init, Fore, Style

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings
from core.mail_client import MailClient

init(autoreset=True)


def test_mail_connection():
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}  TESTE DE CONEXÃO COM SERVIDOR DE E-MAIL (IMAP)")
    print(f"{Fore.CYAN}{'='*60}\n")

    if not settings.is_configured():
        print(f"{Fore.RED}[X] ERRO: Credenciais não configuradas no arquivo .env!")
        print(f"\n{Fore.YELLOW}Para configurar:")
        print("1. Copie o arquivo '.env.example' para '.env'")
        print("2. Preencha seu e-mail em EMAIL_USER")
        print("3. Preencha sua Senha de Aplicativo em EMAIL_PASSWORD")
        print("4. Para Gmail, gere a senha de 16 letras em: https://myaccount.google.com/apppasswords\n")
        sys.exit(1)

    print(f"{Fore.BLUE}[*] Usuário configurado : {Fore.WHITE}{settings.EMAIL_USER}")
    print(f"{Fore.BLUE}[*] Servidor IMAP       : {Fore.WHITE}{settings.IMAP_SERVER}:{settings.IMAP_PORT}")
    print(f"{Fore.BLUE}[*] Caixa de origem     : {Fore.WHITE}{settings.MAILBOX_SOURCE}")
    print(f"{Fore.BLUE}[*] Tentando conectar e autenticar...\n")

    client = MailClient(
        server=settings.IMAP_SERVER,
        port=settings.IMAP_PORT,
        user=settings.EMAIL_USER,
        password=settings.EMAIL_PASSWORD
    )

    try:
        client.connect()
        print(f"{Fore.GREEN}[V] Conexão SSL e Login autenticados com SUCESSO!\n")

        # Testa seleção da caixa de entrada
        client.select_mailbox(settings.MAILBOX_SOURCE)
        unseen_uids = client.search_emails(only_unread=True, limit=5)
        all_uids = client.search_emails(only_unread=False, limit=5)

        print(f"{Fore.GREEN}[V] Caixa '{settings.MAILBOX_SOURCE}' acessada com sucesso.")
        print(f"{Fore.WHITE}    - E-mails não lidos disponíveis: {len(unseen_uids)} (amostra)")
        print(f"{Fore.WHITE}    - Total de e-mails recentes: {len(all_uids)} (amostra)")

        # Lista pastas
        print(f"\n{Fore.BLUE}[*] Listando pastas existentes no servidor:")
        folders = client.list_mailboxes()
        for f in folders[:10]:
            print(f"    - {f}")
        if len(folders) > 10:
            print(f"    ... e mais {len(folders) - 10} pastas.")

        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}  TUDO PRONTO! O SISTEMA ESTÁ APTO A OPERAR.")
        print(f"{Fore.GREEN}{'='*60}\n")

    except Exception as e:
        print(f"\n{Fore.RED}[X] Falha na conexão ou autenticação: {e}\n")
        print(f"{Fore.YELLOW}Dicas de Resolução:")
        if "gmail.com" in settings.IMAP_SERVER.lower():
            print(" -> Para o GMAIL, a autenticação requer uma SENHA DE APP de 16 caracteres:")
            print("    1. Acesse: https://myaccount.google.com/security")
            print("    2. Ative 'Verificação em 2 etapas'")
            print("    3. Acesse: https://myaccount.google.com/apppasswords")
            print("    4. Gere uma senha para 'Automação Python' e cole no .env")
            print("    5. No Gmail web, certifique-se que o IMAP está ativado em:")
            print("       Configurações -> Ver todas as configurações -> Encaminhamento e POP/IMAP -> Ativar IMAP")
        else:
            print(" -> Verifique se a porta (993 para SSL) e o host do servidor estão corretos.")
            print(" -> Verifique se seu provedor exige liberação de acesso externo ou SSL.")
        sys.exit(1)
    finally:
        client.disconnect()


if __name__ == "__main__":
    test_mail_connection()
