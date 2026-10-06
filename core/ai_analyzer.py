import re
import json
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("EmailAutomation")


class AIAnalyzer:
    """Analisador de IA híbrido: integra com Google Gemini / OpenAI e possui fallback heurístico inteligente."""

    def __init__(self, gemini_api_key: str = "", openai_api_key: str = ""):
        self.gemini_key = gemini_api_key.strip()
        self.openai_key = openai_api_key.strip()

    def analyze(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera resumo, nível de urgência, cliente identificado e valor estimado.
        Tenta IA primeiro; se não houver chave ou falhar, usa o motor heurístico.
        """
        # 1. Tenta Gemini se configurado
        if self.gemini_key:
            res = self._call_gemini(email_data)
            if res:
                return res

        # 2. Tenta OpenAI se configurado
        if self.openai_key:
            res = self._call_openai(email_data)
            if res:
                return res

        # 3. Fallback Heurístico Inteligente (Offline e Gratuito)
        return self._heuristic_analysis(email_data)

    def _call_gemini(self, email_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Chamada direta à API do Google Gemini."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
            headers = {"Content-Type": "application/json"}
            prompt = f"""
Você é um assistente corporativo de triagem de e-mails. Analise o e-mail abaixo e responda APENAS um JSON válido.

Remetente: {email_data.get('sender_name')} <{email_data.get('sender_email')}>
Assunto: {email_data.get('subject')}
Conteúdo: {email_data.get('snippet', '')[:600]}

Responda no formato:
{{
  "summary": "Resumo de 1 frase concisa do objetivo do e-mail",
  "urgency": "Alta" | "Média" | "Baixa",
  "client_name": "Nome do cliente ou empresa (ou 'Não identificado')",
  "estimated_value": "Valor financeiro em R$ se houver (ou 'Não informado')",
  "category_hint": "comercial" | "empresa" | "financeiro" | "suporte" | "marketing" | "outros"
}}
"""
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
        except Exception as e:
            logger.warning(f"Aviso: Falha ao consultar Gemini API, acionando fallback: {e}")
        return None

    def _call_openai(self, email_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Chamada direta à API da OpenAI."""
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            prompt = f"""
Analise o e-mail corporativo abaixo e responda APENAS um JSON no formato estrito:
Remetente: {email_data.get('sender_name')} <{email_data.get('sender_email')}>
Assunto: {email_data.get('subject')}
Conteúdo: {email_data.get('snippet', '')[:600]}

JSON esperado:
{{
  "summary": "Resumo de 1 frase concisa",
  "urgency": "Alta" | "Média" | "Baixa",
  "client_name": "Nome ou empresa",
  "estimated_value": "Valor em R$ se houver",
  "category_hint": "comercial" | "empresa" | "financeiro" | "suporte" | "marketing" | "outros"
}}
"""
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                return json.loads(raw_text)
        except Exception as e:
            logger.warning(f"Aviso: Falha ao consultar OpenAI API, acionando fallback: {e}")
        return None

    def _heuristic_analysis(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Motor heurístico avançado de NLP leve sem necessidade de chaves externas."""
        subject = email_data.get("subject", "")
        body = email_data.get("body", "") or email_data.get("snippet", "")
        sender_name = email_data.get("sender_name", "")
        sender_domain = email_data.get("sender_domain", "")

        full_text = f"{subject} {body}".lower()

        # 1. Determina Nível de Urgência
        urgency = "Baixa"
        if any(w in full_text for w in ["urgente", "emergência", "emergencia", "imediato", "vence hoje", "crítico", "critico", "asap", "socorro"]):
            urgency = "Alta"
        elif any(w in full_text for w in ["orçamento", "proposta", "boleto", "reunião", "reuniao", "prazo", "vencimento", "chamado"]):
            urgency = "Média"

        # 2. Extrai Valor Monetário (R$)
        val_match = re.search(r"r\$\s*[\d\.\,]+", full_text)
        estimated_value = val_match.group(0).upper() if val_match else "Não informado"

        # 3. Identifica Nome do Cliente / Empresa
        client_name = sender_name if sender_name else (f"@{sender_domain}" if sender_domain else "Não identificado")

        # 4. Gera Resumo Inteligente em 1 frase
        summary = subject.strip()
        if not summary or summary.lower() in ["(sem assunto)", "sem assunto"]:
            # Pega primeira frase relevante do corpo
            sentences = [s.strip() for s in body.split(".") if len(s.strip()) > 10]
            summary = sentences[0] if sentences else "Mensagem sem texto explicativo"
        else:
            summary = f"Solicitação / Notificação sobre: {summary}"

        return {
            "summary": summary[:140],
            "urgency": urgency,
            "client_name": client_name,
            "estimated_value": estimated_value,
            "category_hint": "heuristica"
        }
