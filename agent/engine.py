"""
Motor de conversa do diagnóstico empreendedor.

Gerencia o loop de conversa: recebe mensagem do usuário, monta contexto
com system prompt + estado + histórico, chama a API DeepSeek, e retorna resposta.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import SYSTEM_PROMPT
from .state import load_state, save_state, save_message, get_history
from .security import sanitize_message, verify_session_owner

# Auto-carrega .env do diretório do projeto
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def _get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY não configurada. Defina no .env ou variável de ambiente.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )


def _build_state_summary(state: dict) -> str:
    """Constrói um resumo textual do estado para incluir no prompt do sistema."""
    parts = []

    # Dores
    dores = state.get("vpc", {}).get("dores", [])
    if dores:
        parts.append("## DORES MAPEADAS")
        for d in dores:
            nivel = d.get("nivel", "?")
            escada = d.get("escada_evidencia", "?")
            parts.append(
                f"- {d['descricao']} [Nível N{nivel}, Escada degrau {escada}]"
            )

    # Tarefas
    tarefas = state.get("vpc", {}).get("tarefas", [])
    if tarefas:
        parts.append("## TAREFAS/JOBS")
        for t in tarefas:
            parts.append(f"- {t['descricao']} [gatilho: {t.get('gatilho', '?')}]")

    # Ganhos
    ganhos = state.get("vpc", {}).get("ganhos", [])
    if ganhos:
        parts.append("## GANHOS")
        for g in ganhos:
            parts.append(f"- {g['descricao']}")

    # Público
    pub = state.get("publico", {})
    if pub.get("segmento_entrada"):
        parts.append(f"## PÚBLICO\n- Segmento de entrada: {pub['segmento_entrada']}")
    if pub.get("segmentos_futuros"):
        parts.append(f"- Segmentos futuros: {', '.join(pub['segmentos_futuros'])}")

    # Jornada
    jornada = state.get("jornada", {}).get("etapas", [])
    if jornada:
        parts.append("## JORNADA")
        for e in jornada:
            parts.append(f"- {e.get('etapa', '?')}: {e.get('acoes', [])}")

    # Gaps pendentes
    gaps = state.get("processo", {}).get("gaps_pendentes", [])
    if gaps:
        parts.append("## GAPS PENDENTES (precisam ser abordados)")
        for g in gaps:
            parts.append(f"- {g}")

    # Sinais de loop
    loop = state.get("processo", {}).get("sinal_loop")
    if loop:
        parts.append(f"## ⚠️ SINAL DE LOOP: {loop}")

    return "\n".join(parts) if parts else "Estado: nenhum dado coletado ainda."


def run_turn(session_id: str, user_id: str, user_message: str) -> str:
    """
    Processa uma mensagem do usuário e retorna a resposta do agente.

    Args:
        session_id: ID da sessão
        user_id: ID do usuário (para verificação de propriedade)
        user_message: Mensagem do usuário (será sanitizada)

    Returns:
        Resposta do agente ou mensagem de erro
    """
    # Verifica propriedade da sessão
    if not verify_session_owner(session_id, user_id):
        return "Erro: sessão não pertence a este usuário."

    # Sanitiza input
    user_message = sanitize_message(user_message)

    state = load_state(session_id)
    if state is None:
        return "Erro: sessão não encontrada."

    # Salva a mensagem do usuário
    save_message(session_id, "user", user_message)

    # Recupera histórico recente
    history = get_history(session_id)

    # Constrói resumo do estado
    state_summary = _build_state_summary(state)

    # Monta mensagens para a API
    messages = [
        {
            "role": "system",
            "content": (
                SYSTEM_PROMPT
                + "\n\n---\n## ESTADO ATUAL DO DIAGNÓSTICO\n"
                + state_summary
                + "\n\nUse este estado como referência. Campos vazios = gaps que precisam ser preenchidos."
                + "\nGaps pendentes DEVEM ser abordados (no gancho natural ou na volta forçada no encerramento)."
                + "\nSe há sinal de loop ativo, NÃO force mais perguntas — encaminhe para encerramento."
            ),
        }
    ]

    # Adiciona histórico como mensagens user/assistant
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Chama a API
    client = _get_client()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )

    answer = response.choices[0].message.content

    # Salva a resposta do agente
    save_message(session_id, "assistant", answer)

    # TODO: em versão futura, parsear a resposta para extrair atualizações de estado
    # (campos preenchidos, gaps fechados, novas confirmações). Por enquanto, o estado
    # é mantido manualmente pelo agente via o resumo incluído no system prompt.

    return answer


def detect_encerramento(state: dict) -> bool:
    """
    Heurística simples para detectar se a sessão pode ser encerrada.
    Retorna True se os campos críticos estiverem razoavelmente preenchidos.
    """
    vpc = state.get("vpc", {})
    dores = vpc.get("dores", [])
    pub = state.get("publico", {})
    loop = state.get("processo", {}).get("sinal_loop")

    # Encerra se há sinal de loop
    if loop:
        return True

    # Encerra se há pelo menos 1 dor mapeada, público definido e proposta de valor
    tem_dor = any(d.get("nivel", 0) >= 3 for d in dores)
    tem_publico = pub.get("segmento_entrada") is not None
    tem_solucao = any(vpc.get("produtos_servicos", []))

    return tem_dor and tem_publico and tem_solucao


def generate_report(session_id: str, user_id: str) -> str:
    """
    Gera o relatório de diagnóstico a partir do histórico completo da conversa.

    Args:
        session_id: ID da sessão
        user_id: ID do usuário (para verificação de propriedade)
    """
    # Verifica propriedade
    if not verify_session_owner(session_id, user_id):
        return "Erro: sessão não pertence a este usuário."

    history = get_history(session_id, limit=200)
    if not history:
        return "Nenhuma conversa encontrada nesta sessão."

    # Constrói transcrição
    transcript = ""
    for msg in history:
        role = "Empreendedor" if msg["role"] == "user" else "Facilitador"
        transcript += f"**{role}:** {msg['content']}\n\n"

    report_prompt = f"""Você é um analista de diagnóstico empreendedor. Abaixo está a transcrição de uma conversa entre um facilitador e um empreendedor. 

Seu trabalho: extrair e estruturar tudo que foi discutido no formato abaixo. Tudo que NÃO foi discutido ou está vago, marque como "⚪ Pendente" ou "🟡 Hipótese". Não invente nada que não está na conversa. Seja conciso e direto.

{transcript}

---
FORMATO EXATO DO RELATÓRIO (siga rigorosamente):

# Diagnóstico de Produto — [nome da ideia]

**Data:** hoje
**Sessões:** 1
**Status:** PARCIAL

---

## 1. Resumo Executivo

[A ideia em 5 linhas: o que o empreendedor quer construir, para quem, qual a dor central, o que foi validado e o que segue como hipótese.]

---

## 2. Value Proposition Canvas

### 2.1 Tarefas (Jobs)

O que o cliente precisa realizar no dia a dia e que a solução deve apoiar.

| # | Tarefa | Contexto (quando) | Gatilho | Confiança |
|---|---|---|---|---|
| T1 | [tarefa] | [quando acontece] | [o que dispara] | 🟢/🟡/⚪ |

### 2.2 Dores

Problemas que atrapalham as tarefas.

[Cada dor como bullet, com nível de confiança]
- **[dor]** 🟢 Validado
  - *Evidência:* "[fala do cliente]"
  - *Custo:* [tempo/dinheiro] | *Alternativa atual:* [o que usa hoje]
- **[dor]** 🟡 Hipótese — *falta:* [o que validaria]

### 2.3 Ganhos

Resultados que o cliente deseja.

| # | Ganho | Resultado observável | Confiança |
|---|---|---|---|
| G1 | [ganho] | [o que muda na prática] | 🟢/🟡/⚪ |

### 2.4 Proposta de Valor

| # | Produto/Serviço | Mecanismo | Alivia dor | Gera ganho | Confiança |
|---|---|---|---|---|---|
| P1 | [solução] | [como funciona] | [dor] | [ganho] | 🟢/🟡/⚪ |

**Aliviadores de dor:** [como remove cada dor]
**Geradores de ganho:** [como produz cada ganho]

---

## 3. Jobs to be Done

Para cada tarefa principal:

### JTBD 1: [tarefa]

| Campo | Descrição | Confiança |
|---|---|---|
| Contexto | [situação que dispara] | 🟢/🟡/⚪ |
| Motivação funcional | [o que precisa ser feito] | 🟢/🟡/⚪ |
| Motivação emocional | [como quer se sentir] | 🟢/🟡/⚪ |
| Motivação social | [como quer ser visto] | 🟢/🟡/⚪ |
| Barreiras | [o que impede] | 🟢/🟡/⚪ |
| Alternativas atuais | [o que usa hoje — concorrente real] | 🟢/🟡/⚪ |

---

## 4. Jornada do Consumidor

| Etapa | Ações | Dores | Canais | Confiança |
|---|---|---|---|---|
| Descoberta | [...] | [...] | [...] | 🟢/🟡/⚪ |
| Consideração | [...] | [...] | [...] | 🟢/🟡/⚪ |
| Decisão | [...] | [...] | [...] | 🟢/🟡/⚪ |
| Uso | [...] | [...] | [...] | 🟢/🟡/⚪ |
| Advocacy | [...] | [...] | [...] | 🟢/🟡/⚪ |

---

## 5. Entendimento de Mercado

### 5.1 Como o mercado opera
[estrutura: quem compra, quem paga, dinâmica]

### 5.2 Concorrentes e alternativas

| Concorrente | O que oferece | Lacuna | Usado hoje? |
|---|---|---|---|
| [...] | [...] | [...] | sim/não |

### 5.3 Diferencial
[por que essa solução seria melhor]

---

## 6. Hipóteses a Validar

- [ ] [hipótese] — *como validar:* [método]

---

## 7. Dados para Lean Canvas (futuro)

| Bloco | Dados coletados |
|---|---|
| Segmentos | [...] |
| Canais | [...] |
| Receita | [...] (disposição a pagar: R$ X) |
| Métricas | [...] |
| Diferencial | [...] |
| Riscos | [...] |

---

## 8. Próximos Passos

- [ ] [gap pendente]
- [ ] [pesquisa de mercado pendente]

---

Legenda: 🟢 Validado (com evidência) | 🟡 Hipótese | ⚪ Pendente

Gere o relatório agora. Sem introduções, sem "segue o relatório", sem enrolação."""

    client = _get_client()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": report_prompt}],
        temperature=0.3,
        max_tokens=3000,
    )

    return response.choices[0].message.content
