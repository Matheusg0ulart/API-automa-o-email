import os
import unittest
from pathlib import Path
from config import settings
from core.classifier import EmailClassifier, normalize_text
from core.reporter import EmailReporter


class TestEmailAutomation(unittest.TestCase):
    def setUp(self):
        self.rules = settings.load_rules()
        self.classifier = EmailClassifier(self.rules, company_domain="minhaempresa.com.br")
        self.reporter = EmailReporter(settings.REPORTS_DIR)

    def test_text_normalization(self):
        text = "PROPOSTA DE COTAÇÃO & ORÇAMENTO / NÃO PERCA!"
        normalized = normalize_text(text)
        self.assertIn("proposta", normalized)
        self.assertIn("cotacao", normalized)
        self.assertIn("orcamento", normalized)
        self.assertNotIn("ç", normalized)
        self.assertNotIn("ã", normalized)

    def test_classification_comercial(self):
        email_data = {
            "subject": "Solicitação de Orçamento e Proposta Comercial",
            "sender_email": "compras@cliente.com.br",
            "sender_domain": "cliente.com.br",
            "body": "Prezados, gostaríamos de solicitar um orçamento e tabela de preços para aquisição de novos produtos."
        }
        res = self.classifier.classify(email_data)
        self.assertEqual(res["category_id"], "comercial")
        self.assertEqual(res["target_folder"], "Comercial")
        self.assertGreaterEqual(res["score"], 2.0)

    def test_classification_empresa(self):
        email_data = {
            "subject": "Ata da Reunião de Diretoria e Comunicado Geral",
            "sender_email": "rh@minhaempresa.com.br",
            "sender_domain": "minhaempresa.com.br",
            "body": "Segue o comunicado interno e o alinhamento da equipe para a sprint de planejamento."
        }
        res = self.classifier.classify(email_data)
        self.assertEqual(res["category_id"], "empresa")
        self.assertEqual(res["target_folder"], "Empresa")
        self.assertGreaterEqual(res["score"], 2.0)

    def test_classification_financeiro(self):
        email_data = {
            "subject": "Envio de Boleto Bancário e Nota Fiscal NF-e",
            "sender_email": "financeiro@fornecedor.com.br",
            "sender_domain": "fornecedor.com.br",
            "body": "Segue anexa a DANFE e a linha digitável para quitação com vencimento em 10/10."
        }
        res = self.classifier.classify(email_data)
        self.assertEqual(res["category_id"], "financeiro")
        self.assertEqual(res["target_folder"], "Financeiro")
        self.assertGreaterEqual(res["score"], 2.0)

    def test_classification_suporte(self):
        email_data = {
            "subject": "Chamado #48291 - Erro ao emitir relatório no sistema",
            "sender_email": "usuario@outrodominio.com.br",
            "sender_domain": "outrodominio.com.br",
            "body": "Estou com um bug grave na plataforma. Preciso de suporte urgente da equipe."
        }
        res = self.classifier.classify(email_data)
        self.assertEqual(res["category_id"], "suporte")
        self.assertEqual(res["target_folder"], "Suporte")
        self.assertGreaterEqual(res["score"], 2.0)

    def test_classification_marketing(self):
        email_data = {
            "subject": "Imperdível! Aproveite até 50% de Desconto na Black Friday",
            "sender_email": "news@loja.com.br",
            "sender_domain": "loja.com.br",
            "body": "Clique aqui para ver nossas ofertas especiais. Se não quiser mais receber, clique em descadastre-se."
        }
        res = self.classifier.classify(email_data)
        self.assertEqual(res["category_id"], "marketing")
        self.assertEqual(res["target_folder"], "Marketing")
        self.assertGreaterEqual(res["score"], 2.0)

    def test_classification_outros(self):
        email_data = {
            "subject": "Olá amigo, como você está?",
            "sender_email": "amigo@gmail.com",
            "sender_domain": "gmail.com",
            "body": "Faz tempo que não conversamos. Um abraço."
        }
        res = self.classifier.classify(email_data)
        self.assertEqual(res["category_id"], "outros")
        self.assertEqual(res["target_folder"], "Outros")

    def tearDown(self):
        # Limpa relatórios temporários criados nos testes
        for f in settings.REPORTS_DIR.glob("simulacao_emails_*.*"):
            try:
                f.unlink()
            except Exception:
                pass

    def test_report_generation(self):
        records = [
            {
                "uid": "101",
                "date": "2026-10-06 09:00",
                "sender_name": "João Vendas",
                "sender_email": "joao@compras.com",
                "subject": "Proposta de Serviço",
                "category_id": "comercial",
                "category_name": "Comercial / Vendas",
                "target_folder": "Comercial",
                "score": 6.0,
                "reasons": ["Assunto: proposta"],
                "status": "[SIMULAÇÃO] Direcionaria para: Comercial",
                "snippet": "Olá, segue a proposta..."
            },
            {
                "uid": "102",
                "date": "2026-10-06 09:10",
                "sender_name": "RH Corporativo",
                "sender_email": "rh@minhaempresa.com.br",
                "subject": "Comunicado de Férias",
                "category_id": "empresa",
                "category_name": "Empresa / Operacional",
                "target_folder": "Empresa",
                "score": 13.0,
                "reasons": ["Domínio da empresa", "Assunto: comunicado"],
                "status": "[SIMULAÇÃO] Direcionaria para: Empresa",
                "snippet": "Prezados colaboradores..."
            }
        ]
        result = self.reporter.generate_report(records, dry_run=True)
        self.assertTrue(Path(result["xlsx_path"]).exists())
        self.assertTrue(Path(result["csv_path"]).exists())
        self.assertEqual(result["total_processed"], 2)
        self.assertEqual(result["categories_breakdown"]["Comercial / Vendas"], 1)
        self.assertEqual(result["categories_breakdown"]["Empresa / Operacional"], 1)

    def test_ai_analyzer_heuristic(self):
        from core.ai_analyzer import AIAnalyzer
        ai = AIAnalyzer()
        email_data = {
            "subject": "Solicitação urgente de proposta comercial",
            "body": "Precisamos de um orçamento de R$ 45.000,00 para aprovação hoje.",
            "sender_name": "Carlos Diretor",
            "sender_email": "carlos@parceiro.com",
            "sender_domain": "parceiro.com",
            "snippet": "Precisamos de um orçamento de R$ 45.000,00 para aprovação hoje."
        }
        res = ai.analyze(email_data)
        self.assertEqual(res["urgency"], "Alta")
        self.assertIn("45.000", res["estimated_value"])
        self.assertEqual(res["client_name"], "Carlos Diretor")
        self.assertTrue(len(res["summary"]) > 0)

    def test_database_and_metrics(self):
        from core.database import Database
        import tempfile
        temp_db = Path(tempfile.gettempdir()) / "test_emails.db"
        if temp_db.exists():
            temp_db.unlink()

        db = Database(db_path=temp_db)
        record = {
            "uid": "999",
            "date": "2026-10-06 10:00",
            "sender_name": "Maria",
            "sender_email": "maria@cliente.com",
            "sender_domain": "cliente.com",
            "subject": "Pedido Comercial",
            "category_id": "comercial",
            "category_name": "Comercial / Vendas",
            "target_folder": "Comercial",
            "score": 5.0,
            "reasons": ["Assunto: pedido"],
            "status": "Movido",
            "summary": "Pedido de compras",
            "urgency": "Média",
            "estimated_value": "R$ 10.000,00",
            "auto_replied": True,
            "is_dry_run": False
        }
        db.save_email(record)
        recent = db.get_recent(10)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["subject"], "Pedido Comercial")

        metrics = db.get_metrics()
        self.assertEqual(metrics["total_emails"], 1)
        self.assertEqual(metrics["auto_replies_sent"], 1)
        self.assertTrue(db.is_replied("999"))

        if temp_db.exists():
            temp_db.unlink()

    def test_auto_responder_rules(self):
        from core.auto_reply import AutoResponder
        responder = AutoResponder(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            user="me@empresa.com",
            password="pwd",
            enabled=True
        )
        # Deve responder comercial normal
        self.assertTrue(responder.should_reply({"sender_email": "cliente@externo.com"}, "comercial"))
        # Não deve responder outras categorias
        self.assertFalse(responder.should_reply({"sender_email": "cliente@externo.com"}, "empresa"))
        # Não deve responder no-reply
        self.assertFalse(responder.should_reply({"sender_email": "no-reply@externo.com"}, "comercial"))
        # Não deve responder a própria conta
        self.assertFalse(responder.should_reply({"sender_email": "me@empresa.com"}, "comercial"))

    def test_api_endpoints(self):
        from api.app import classify_text, ClassifyRequest, get_dashboard_data, get_system_status
        status = get_system_status()
        self.assertEqual(status["status"], "online")

        req = ClassifyRequest(
            subject="Orçamento de software e licenças comerciais",
            body="Gostaria de fechar um contrato no valor de R$ 30.000,00.",
            sender_email="contato@comprador.com.br"
        )
        res = classify_text(req)
        self.assertEqual(res["category_id"], "comercial")
        self.assertEqual(res["ai_insights"]["urgency"], "Média")
        self.assertIn("30.000", res["ai_insights"]["estimated_value"])

        dash_data = get_dashboard_data()
        self.assertIn("metrics", dash_data)
        self.assertIn("recent_emails", dash_data)


if __name__ == "__main__":
    unittest.main()
