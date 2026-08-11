"""
Geração de relatório de diagnóstico (parcial ou final).

Formata o estado da sessão em markdown estruturado com níveis de confiança.
"""

from .state import load_state


def gerar_relatorio(session_id: str) -> str:
    """
    Gera o relatório de diagnóstico a partir do estado da sessão.

    Retorna uma string markdown com:
    - Resumo executivo
    - Dores e soluções (com nível de confiança)
    - Jornada do consumidor
    - Público-alvo
    - Hipóteses a validar
    - Gaps pendentes
    """
    state = load_state(session_id)
    if state is None:
        return "Erro: sessão não encontrada."

    vpc = state.get("vpc", {})
    pub = state.get("publico", {})
    jornada = state.get("jornada", {})
    lean = state.get("lean_futuro", {})
    processo = state.get("processo", {})

    lines = []
    lines.append("# Diagnóstico Empreendedor\n")

    # --- Resumo Executivo ---
    lines.append("## Resumo Executivo\n")
    ideia = _extrair_ideia(state)
    lines.append(ideia)
    lines.append("")

    # --- Dores ---
    dores = vpc.get("dores", [])
    if dores:
        lines.append("## Dores e Problemas\n")
        for d in dores:
            conf = _nivel_confianca(d)
            lines.append(f"- **{d.get('descricao', '???')}** {conf}")
            if d.get("evidencia"):
                lines.append(f"  - Evidência: {d['evidencia']}")
            if d.get("consequencia"):
                lines.append(f"  - Consequência: {d['consequencia']}")
            if d.get("tentativa_atual"):
                lines.append(f"  - Solução atual (gambiarra): {d['tentativa_atual']}")
        lines.append("")

    # --- Tarefas/Jobs ---
    tarefas = vpc.get("tarefas", [])
    if tarefas:
        lines.append("## Tarefas e Jobs\n")
        for t in tarefas:
            lines.append(f"- {t.get('descricao', '???')}")
            if t.get("gatilho"):
                lines.append(f"  - Gatilho: {t['gatilho']}")
            if t.get("contexto_uso"):
                lines.append(f"  - Contexto: {t['contexto_uso']}")
        lines.append("")

    # --- Ganhos ---
    ganhos = vpc.get("ganhos", [])
    if ganhos:
        lines.append("## Ganhos Desejados\n")
        for g in ganhos:
            lines.append(f"- {g.get('descricao', '???')}")
        lines.append("")

    # --- Proposta de Valor ---
    produtos = vpc.get("produtos_servicos", [])
    aliviadores = vpc.get("aliviadores_dor", [])
    geradores = vpc.get("geradores_ganho", [])
    if produtos or aliviadores or geradores:
        lines.append("## Proposta de Valor\n")
        for p in produtos:
            conf = _nivel_confianca(p)
            lines.append(f"- **Solução:** {p.get('descricao', '???')} {conf}")
            if p.get("mecanismo"):
                lines.append(f"  - Mecanismo: {p['mecanismo']}")
        for a in aliviadores:
            lines.append(f"- Aliviador de dor: {a.get('descricao', '???')}")
        for g in geradores:
            lines.append(f"- Gerador de ganho: {g.get('descricao', '???')}")
        lines.append("")

    # --- Jornada ---
    etapas = jornada.get("etapas", [])
    if etapas:
        lines.append("## Jornada do Consumidor\n")
        for e in etapas:
            conf = _nivel_confianca(e)
            lines.append(f"### {e.get('etapa', '???').capitalize()} {conf}")
            if e.get("acoes"):
                lines.append(f"- Ações: {', '.join(e['acoes'])}")
            if e.get("dores"):
                lines.append(f"- Dores: {', '.join(e['dores'])}")
            if e.get("canais"):
                lines.append(f"- Canais: {', '.join(e['canais'])}")
        lines.append("")

    # --- Público ---
    if pub.get("segmento_entrada"):
        lines.append("## Público-Alvo\n")
        lines.append(f"- **Segmento de entrada (MVP):** {pub['segmento_entrada']}")
        if pub.get("justificativa"):
            lines.append(f"  - Justificativa: {pub['justificativa']}")
        futuros = pub.get("segmentos_futuros", [])
        if futuros:
            lines.append(f"- Segmentos futuros: {', '.join(futuros)}")
        lines.append("")

    # --- Disposição a Pagar ---
    receitas = lean.get("fontes_receita", [])
    if receitas:
        lines.append("## Disposição a Pagar\n")
        for r in receitas:
            if isinstance(r, dict):
                lines.append(f"- {r.get('descricao', r.get('disposicao_a_pagar', '???'))}")
            else:
                lines.append(f"- {r}")
        lines.append("")

    # --- Hipóteses ---
    hipoteses = processo.get("hipoteses_a_validar", [])
    gaps = processo.get("gaps_pendentes", [])
    if hipoteses or gaps:
        lines.append("## Hipóteses a Validar\n")
        for h in hipoteses:
            if isinstance(h, dict):
                lines.append(f"- 🔶 {h.get('hipotese', h.get('descricao', str(h)))}")
            else:
                lines.append(f"- 🔶 {h}")
        for g in gaps:
            if isinstance(g, dict):
                lines.append(f"- ⚪ {g.get('campo', g.get('descricao', str(g)))}")
            else:
                lines.append(f"- ⚪ {g}")
        lines.append("")

    # --- Status do processo ---
    confirmacoes = processo.get("confirmacoes", [])
    sinal_loop = processo.get("sinal_loop")
    lines.append("## Status da Sessão\n")
    lines.append(f"- Confirmações do cliente: {len(confirmacoes)}")
    if sinal_loop:
        lines.append(f"- ⚠️ Sinal de loop detectado: {sinal_loop}")
    lines.append("")

    # Legenda
    lines.append("---\n")
    lines.append("**Legenda:** ✅ Validado | 🔶 Hipótese | ⚪ Pendente\n")
    lines.append("*Este é um diagnóstico parcial. Campos marcados como hipótese ou pendente precisam de validação adicional.*")

    return "\n".join(lines)


def _nivel_confianca(item: dict) -> str:
    """Retorna o emoji de confiança baseado no nível e confirmação."""
    confirmado = item.get("confirmado", False)
    nivel = item.get("nivel", 0)

    if nivel >= 3 and confirmado:
        return "✅ Validado"
    elif nivel >= 2:
        return "🔶 Hipótese"
    else:
        return "⚪ Pendente"


def _extrair_ideia(state: dict) -> str:
    """Tenta extrair a ideia central do estado."""
    vpc = state.get("vpc", {})
    pub = state.get("publico", {})

    produtos = vpc.get("produtos_servicos", [])
    solucao = produtos[0].get("descricao", "") if produtos else ""

    publico = pub.get("segmento_entrada", "")

    dores = vpc.get("dores", [])
    dor_principal = dores[0].get("descricao", "") if dores else ""

    if solucao and publico:
        return f"**Ideia:** {solucao} para {publico}."
    elif solucao:
        return f"**Ideia:** {solucao}."
    elif dor_principal:
        return f"**Dor identificada:** {dor_principal}."
    else:
        return "Ideia ainda não completamente mapeada. Continue a conversa para refinar."
