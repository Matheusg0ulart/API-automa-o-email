import argparse
import logging
import sys
import time
from datetime import datetime
from colorama import init, Fore, Style

# Garante suporte a UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import settings
from core.organizer import EmailOrganizer
from test_connection import test_mail_connection

init(autoreset=True)

# Configuração de Log para arquivo e terminal
log_filename = settings.LOGS_DIR / f"automacao_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EmailAutomation")


def print_banner():
    banner = f"""
{Fore.CYAN}======================================================================
             AUTOMAÇÃO INTELIGENTE DE E-MAILS & GMAIL                 
             Triagem Comercial, Corporativa e Financeira              
======================================================================{Style.RESET_ALL}
"""
    print(banner)


def display_results_summary(result: dict):
    """Exibe um resumo elegante no console após o processamento."""
    print(f"\n{Fore.GREEN}{'='*65}")
    mode_text = f"{Fore.YELLOW}[MODO SIMULAÇÃO - NADA FOI MOVIDO]" if result["dry_run"] else f"{Fore.GREEN}[MODO PRODUÇÃO - E-MAILS MOVIDOS]"
    print(f"  RESUMO DA EXECUÇÃO {mode_text}")
    print(f"{Fore.GREEN}{'='*65}\n")

    total = result["processed_count"]
    print(f"{Fore.WHITE}Total de e-mails processados: {Fore.YELLOW}{total}")

    if total == 0:
        print(f"{Fore.CYAN}Nenhum e-mail novo encontrado para processar no momento.")
        return

    report_info = result.get("report")
    if report_info:
        print(f"\n{Fore.BLUE}Distribuição por Categoria:")
        for cat_name, count in report_info.get("categories_breakdown", {}).items():
            print(f"  • {cat_name:<30}: {count} e-mail(s)")

        print(f"\n{Fore.MAGENTA}Relatórios Gerados:")
        print(f"  [Excel] {report_info.get('xlsx_path')}")
        print(f"  [CSV]   {report_info.get('csv_path')}")

    print(f"\n{Fore.GREEN}{'='*65}\n")


def run_single_execution(dry_run: bool, limit: int = None, only_unread: bool = None):
    """Executa uma rodada de triagem."""
    if not settings.is_configured():
        print(f"\n{Fore.RED}[X] Erro: Arquivo .env não está configurado com suas credenciais!")
        print(f"{Fore.YELLOW}Abra o arquivo .env e informe EMAIL_USER e EMAIL_PASSWORD antes de continuar.\n")
        return

    print(f"\n{Fore.CYAN}[*] Iniciando triagem de e-mails...")
    try:
        organizer = EmailOrganizer(dry_run=dry_run)
        result = organizer.process_emails(limit=limit, only_unread=only_unread)
        display_results_summary(result)
    except Exception as e:
        logger.error(f"Erro durante o processamento: {e}")
        print(f"\n{Fore.RED}[X] Ocorreu uma falha: {e}\n")


def run_continuous_monitoring(dry_run: bool, interval_minutes: int, limit: int = 20):
    """Executa o monitoramento em loop contínuo."""
    if not settings.is_configured():
        print(f"\n{Fore.RED}[X] Erro: Credenciais não configuradas no .env!\n")
        return

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}  INICIANDO MODO DE MONITORAMENTO CONTÍNUO")
    print(f"{Fore.CYAN}  Intervalo: A cada {interval_minutes} minuto(s) | Simulação: {dry_run}")
    print(f"{Fore.CYAN}  (Pressione Ctrl+C para encerrar)")
    print(f"{Fore.CYAN}{'='*60}\n")

    try:
        round_num = 1
        while True:
            print(f"\n{Fore.YELLOW}[Rodada {round_num}] {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} - Verificando novos e-mails...")
            try:
                organizer = EmailOrganizer(dry_run=dry_run)
                result = organizer.process_emails(limit=limit, only_unread=True)
                if result["processed_count"] > 0:
                    display_results_summary(result)
                else:
                    print(f"{Fore.CYAN}Nenhum e-mail novo não lido.")
            except Exception as e:
                logger.error(f"Falha na rodada {round_num}: {e}")

            round_num += 1
            print(f"{Fore.BLUE}Aguardando {interval_minutes} minuto(s) para a próxima checagem...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}[!] Monitoramento contínuo finalizado pelo usuário.\n")


def show_current_rules():
    """Exibe as regras e categorias cadastradas no rules.json."""
    rules = settings.load_rules()
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}  CATEGORIAS E REGRAS CONFIGURADAS")
    print(f"{Fore.CYAN}{'='*60}\n")

    for cat in rules.get("categories", []):
        print(f"{Fore.GREEN}[*] {cat['name']} (Pasta Destino: '{cat['folder']}')")
        print(f"    {Fore.WHITE}Descrição: {cat.get('description', '')}")
        sample_subj = ", ".join(cat.get("keywords_subject", [])[:5])
        print(f"    {Fore.YELLOW}Exemplos Assunto: {sample_subj}...")
        sample_body = ", ".join(cat.get("keywords_body", [])[:5])
        print(f"    {Fore.CYAN}Exemplos Corpo  : {sample_body}...")
        print()

    print(f"{Fore.WHITE}Pasta padrão para não identificados: {Fore.YELLOW}'{rules.get('default_folder', 'Outros')}'")
    print(f"{Fore.WHITE}Arquivo de edição: {Fore.YELLOW}{settings.RULES_FILE}\n")


def start_web_server():
    """Inicia o servidor FastAPI e o Painel Web."""
    import uvicorn
    print(f"\n{Fore.GREEN}{'='*60}")
    print(f"{Fore.GREEN}  INICIANDO SERVIDOR WEB E PAINEL DASHBOARD (FASTAPI)")
    print(f"{Fore.GREEN}{'='*60}")
    print(f"{Fore.CYAN}  * Painel Visual : {Fore.WHITE}http://{settings.WEB_HOST}:{settings.WEB_PORT}")
    print(f"{Fore.CYAN}  * Swagger Docs  : {Fore.WHITE}http://{settings.WEB_HOST}:{settings.WEB_PORT}/docs")
    print(f"{Fore.YELLOW}  (Pressione Ctrl+C para encerrar o servidor)\n")
    uvicorn.run("api.app:app", host=settings.WEB_HOST, port=settings.WEB_PORT, reload=False)


def interactive_menu():
    """Menu interativo no terminal."""
    while True:
        print_banner()
        print(f"{Fore.WHITE}Selecione uma opção:")
        print(f"  {Fore.GREEN}[1]{Fore.WHITE} 🚀 Executar Filtragem e Separação Agora (Mover no servidor)")
        print(f"  {Fore.YELLOW}[2]{Fore.WHITE} 🧪 Modo Simulação / Teste Seguro (Não move nada, gera relatório)")
        print(f"  {Fore.BLUE}[3]{Fore.WHITE} 📊 Gerar Relatório dos Últimos E-mails (Lidos e Não Lidos)")
        print(f"  {Fore.MAGENTA}[4]{Fore.WHITE} 🔄 Iniciar Monitoramento Contínuo Automático")
        print(f"  {Fore.CYAN}[5]{Fore.WHITE} 🌐 Iniciar Painel Web e API REST (Dashboard / Swagger)")
        print(f"  {Fore.CYAN}[6]{Fore.WHITE} 🔌 Testar Conexão com o E-mail / Gmail")
        print(f"  {Fore.WHITE}[7] ⚙️ Visualizar Regras e Categorias Atuais")
        print(f"  {Fore.RED}[8]{Fore.WHITE} ❌ Sair\n")

        choice = input(f"{Fore.GREEN}Digite o número da opção desejada: {Style.RESET_ALL}").strip()

        if choice == "1":
            confirm = input(f"{Fore.YELLOW}Deseja realmente processar e MOVER os e-mails no servidor? (s/N): ").strip().lower()
            if confirm in ("s", "sim", "y", "yes"):
                run_single_execution(dry_run=False)
            else:
                print(f"{Fore.CYAN}Operação cancelada.")
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "2":
            run_single_execution(dry_run=True)
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "3":
            try:
                qtd_input = input("Quantos e-mails recentes deseja analisar? (Padrão: 30): ").strip()
                qtd = int(qtd_input) if qtd_input.isdigit() else 30
                run_single_execution(dry_run=True, limit=qtd, only_unread=False)
            except Exception as e:
                print(f"{Fore.RED}Erro: {e}")
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "4":
            interval_str = input(f"Informe o intervalo em minutos (Padrão: {settings.MONITOR_INTERVAL_MINUTES} min): ").strip()
            interval = int(interval_str) if interval_str.isdigit() else settings.MONITOR_INTERVAL_MINUTES
            mode_str = input("Executar em modo real de mover e-mails? (s/N, padrão N=simulação): ").strip().lower()
            is_dry = mode_str not in ("s", "sim", "y", "yes")
            run_continuous_monitoring(dry_run=is_dry, interval_minutes=interval)
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "5":
            try:
                start_web_server()
            except KeyboardInterrupt:
                pass
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "6":
            try:
                test_mail_connection()
            except SystemExit:
                pass
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "7":
            show_current_rules()
            input(f"\n{Fore.WHITE}Pressione ENTER para voltar ao menu...")

        elif choice == "8":
            print(f"\n{Fore.GREEN}Encerrando aplicação. Até mais!\n")
            break
        else:
            print(f"\n{Fore.RED}Opção inválida! Tente novamente.\n")
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Automação Completa de E-mails e Gmail com Triagem Inteligente.")
    parser.add_argument("--run", action="store_true", help="Executa a separação e movimentação de e-mails em produção.")
    parser.add_argument("--dry-run", action="store_true", help="Executa em modo de simulação (apenas analisa e gera relatório).")
    parser.add_argument("--monitor", action="store_true", help="Inicia o monitoramento contínuo em loop.")
    parser.add_argument("--web", action="store_true", help="Inicia o servidor web com Dashboard e API REST FastAPI.")
    parser.add_argument("--interval", type=int, default=settings.MONITOR_INTERVAL_MINUTES, help="Intervalo em minutos para monitoramento contínuo.")
    parser.add_argument("--limit", type=int, default=settings.MAX_EMAILS_PER_RUN, help="Limite de e-mails para processar.")
    parser.add_argument("--all", action="store_true", help="Processa todos os e-mails (não apenas os não lidos).")
    parser.add_argument("--test", action="store_true", help="Executa o teste de conexão com o e-mail.")
    parser.add_argument("--rules", action="store_true", help="Exibe as regras atuais configuradas.")

    args = parser.parse_args()

    # Se nenhum argumento de linha de comando for fornecido, abre o menu interativo
    if len(sys.argv) == 1:
        interactive_menu()
        return

    if args.web:
        start_web_server()
    elif args.test:
        test_mail_connection()
    elif args.rules:
        show_current_rules()
    elif args.monitor:
        run_continuous_monitoring(dry_run=args.dry_run, interval_minutes=args.interval, limit=args.limit)
    elif args.run or args.dry_run:
        dry_run_flag = True if args.dry_run else False
        only_unread = not args.all
        run_single_execution(dry_run=dry_run_flag, limit=args.limit, only_unread=only_unread)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
