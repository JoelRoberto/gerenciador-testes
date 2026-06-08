import pandas as pd
import streamlit as st
from fpdf import FPDF

st.set_page_config(page_title="Gerenciador de Casos de Teste", layout="wide")

try:
    from dados import CASOS_DE_TESTE, PASSOS_EXECUCAO
except Exception as e:
    st.error(f"❌ Erro ao carregar o arquivo dados.py: {e}")
    st.stop()

MAPEAMENTO_SECOES = {
    1: "🚀 SEÇÃO LAUNCHER",
    10: "💳 SEÇÃO PAGAMENTO",
    61: "❌ SEÇÃO CANCELAMENTO",
    72: "🔌 SEÇÃO CONEXÃO",
    87: "🔓 SEÇÃO ATIVAÇÃO",
    98: "⚙️ SEÇÃO AJUSTES",
    114: "❓ SEÇÃO AJUDA",
    122: "🧮 SEÇÃO CALCULADORA",
    125: "📊 SEÇÃO SIMULADOR DE VENDAS",
    133: "🧾 SEÇÃO REIMPRESSÃO / RECIBOS",
    142: "📈 SEÇÃO RELATÓRIO",
    151: "🔒 SEÇÃO FECHAMENTO",
    157: "🏪 SEÇÃO LOJA",
    162: "✨ SEÇÃO NOVIDADES"
}

OPCOES_STATUS = ["Não Executado", "Aprovado ✅", "Reprovado ❌", "Não Aplicável ⚠️"]
STATUS_COM_OBSERVACAO = {"Reprovado ❌", "Não Aplicável ⚠️"}


class RelatorioPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(26, 54, 93)
        self.cell(0, 10, "Relatorio de Execucao de Testes", ln=True)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(160, 174, 192)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="R")


def tratar_texto_pdf(texto):
    if not texto:
        return ""
    texto = str(texto)
    texto = (texto
             .replace("✅", "[Aprovado]")
             .replace("❌", "[Reprovado]")
             .replace("⚠️", "[Nao Aplicavel]")
             .replace("⚡", ""))

    substituicoes = {
        "á": "a", "à": "a", "ã": "a", "â": "a", "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "é": "e", "è": "e", "ê": "e", "É": "E", "È": "E", "Ê": "E",
        "í": "i", "ì": "i", "î": "i", "Í": "I", "Ì": "I", "Î": "I",
        "ó": "o", "ò": "o", "ô": "o", "õ": "o", "Ó": "O", "Ò": "O", "Ô": "O", "Õ": "O",
        "ú": "u", "ù": "u", "û": "u", "Ú": "U", "Ù": "U", "Û": "U",
        "ç": "c", "Ç": "C", "º": ".", "ª": ".", "–": "-", "—": "-",
        "'": "'", "'": "'", "\u201c": '"', "\u201d": '"'
    }
    for original, substituto in substituicoes.items():
        texto = texto.replace(original, substituto)

    return texto.encode('latin-1', 'ignore').decode('latin-1')


def gerar_pdf_fpdf(df_base, resultados, observacoes):
    df = df_base.copy()
    df["Resultado"] = df["ID"].map(lambda x: resultados.get(x, "Não Executado"))
    df["Observacao"] = df["ID"].map(lambda x: observacoes.get(x, ""))

    qtd_total = len(df)
    qtd_aprovado = len(df[df["Resultado"] == "Aprovado ✅"])
    qtd_reprovado = len(df[df["Resultado"] == "Reprovado ❌"])
    qtd_nao_aplic = len(df[df["Resultado"] == "Não Aplicável ⚠️"])
    qtd_nao_exec = qtd_total - (qtd_aprovado + qtd_reprovado + qtd_nao_aplic)

    pdf = RelatorioPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Resumo executivo
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 8, "Resumo Executivo da Rodada:", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(240, 244, 248)
    pdf.cell(35, 10, f" Total: {qtd_total}", border=1, fill=True)
    pdf.set_fill_color(230, 255, 250)
    pdf.cell(38, 10, f" Aprovado: {qtd_aprovado}", border=1, fill=True)
    pdf.set_fill_color(255, 245, 245)
    pdf.cell(38, 10, f" Reprovado: {qtd_reprovado}", border=1, fill=True)
    pdf.set_fill_color(255, 250, 240)
    pdf.cell(38, 10, f" Nao Aplicavel: {qtd_nao_aplic}", border=1, fill=True)
    pdf.set_fill_color(247, 250, 252)
    pdf.cell(41, 10, f" Nao Exec.: {qtd_nao_exec}", border=1, fill=True, ln=True)
    pdf.ln(8)

    # Cabeçalho da tabela
    w_id, w_caso, w_passos, w_status = 18, 54, 93, 25
    largura_total = w_id + w_caso + w_passos + w_status

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(43, 108, 176)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(w_id, 10, "ID", border=1, fill=True, align="C")
    pdf.cell(w_caso, 10, " Caso de Teste", border=1, fill=True)
    pdf.cell(w_passos, 10, " Passos de Execucao", border=1, fill=True)
    pdf.cell(w_status, 10, "Resultado", border=1, fill=True, ln=True, align="C")

    h_linha_texto = 4.5

    for _, row in df.iterrows():
        status_original = str(row["Resultado"])
        status_limpo = (status_original
                        .replace(" ✅", "")
                        .replace(" ❌", "")
                        .replace(" ⚠️", ""))

        caso_limpo = tratar_texto_pdf(row["Caso de Teste"])
        passos_limpo = tratar_texto_pdf(row["Descrição / Passos"])
        obs_raw = str(row["Observacao"]).strip() if row["Observacao"] else ""
        obs_limpo = tratar_texto_pdf(obs_raw) if obs_raw else ""

        linhas_caso = len(pdf.multi_cell(w_caso - 4, h_linha_texto, caso_limpo, split_only=True))
        linhas_passos = len(pdf.multi_cell(w_passos - 4, h_linha_texto, passos_limpo, split_only=True))
        max_linhas = max(linhas_caso, linhas_passos, 1)
        altura_linha_principal = (max_linhas * h_linha_texto) + 6

        # Altura da linha de observação (apenas se houver)
        obs_label = "Observacao: "
        obs_texto_completo = obs_label + obs_limpo if obs_limpo else ""
        linhas_obs = len(pdf.multi_cell(largura_total - 6, h_linha_texto, obs_texto_completo, split_only=True)) if obs_limpo else 0
        altura_obs = (linhas_obs * h_linha_texto) + 4 if obs_limpo else 0

        altura_total_bloco = altura_linha_principal + altura_obs

        if pdf.get_y() + altura_total_bloco > 275:
            pdf.add_page()

        x, y = pdf.get_x(), pdf.get_y()

        # Bordas da linha principal
        pdf.rect(x, y, w_id, altura_linha_principal)
        pdf.rect(x + w_id, y, w_caso, altura_linha_principal)
        pdf.rect(x + w_id + w_caso, y, w_passos, altura_linha_principal)

        # Célula de status colorida
        if "Aprovado" in status_original:
            pdf.set_fill_color(230, 255, 250)
            pdf.set_text_color(35, 78, 82)
        elif "Reprovado" in status_original:
            pdf.set_fill_color(255, 245, 245)
            pdf.set_text_color(116, 42, 42)
        elif "Nao Aplicavel" in status_limpo or "Não Aplicável" in status_original:
            pdf.set_fill_color(255, 250, 240)
            pdf.set_text_color(123, 52, 30)
        else:
            pdf.set_fill_color(247, 250, 252)
            pdf.set_text_color(74, 85, 104)

        pdf.rect(x + w_id + w_caso + w_passos, y, w_status, altura_linha_principal, style="F")
        pdf.rect(x + w_id + w_caso + w_passos, y, w_status, altura_linha_principal)

        # ID
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(43, 108, 176)
        pdf.set_xy(x, y + (altura_linha_principal / 2) - 2)
        pdf.cell(w_id, 4, str(row["ID"]), align="C")

        # Caso de Teste
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(45, 55, 72)
        pdf.set_xy(x + w_id + 2, y + 3)
        pdf.multi_cell(w_caso - 4, h_linha_texto, caso_limpo)

        # Passos
        pdf.set_xy(x + w_id + w_caso + 2, y + 3)
        pdf.multi_cell(w_passos - 4, h_linha_texto, passos_limpo)

        # Status label
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(x + w_id + w_caso + w_passos, y + (altura_linha_principal / 2) - 2)
        pdf.cell(w_status, 4, status_limpo, align="C")

        # Linha de observação (opção B: linha adicional abaixo, só se houver)
        y_obs = y + altura_linha_principal
        if obs_limpo:
            if "Reprovado" in status_original:
                pdf.set_fill_color(255, 235, 235)
                pdf.set_text_color(116, 42, 42)
            else:  # Não Aplicável
                pdf.set_fill_color(255, 244, 225)
                pdf.set_text_color(123, 52, 30)

            pdf.rect(x, y_obs, largura_total, altura_obs, style="F")
            pdf.rect(x, y_obs, largura_total, altura_obs)

            pdf.set_font("Helvetica", "B", 8)
            pdf.set_xy(x + 3, y_obs + 2)
            pdf.write(h_linha_texto, obs_label)

            pdf.set_font("Helvetica", "", 8)
            pdf.set_xy(x + 3 + pdf.get_string_width(obs_label), y_obs + 2)
            pdf.multi_cell(largura_total - 6 - pdf.get_string_width(obs_label), h_linha_texto, obs_limpo)

        pdf.set_xy(10, y_obs + altura_obs)

    return bytes(pdf.output())


def atualizar_status(id_teste):
    st.session_state.resultados[id_teste] = st.session_state[f"status_{id_teste}"]
    # Limpa observação se status voltou para sem-observação
    if st.session_state.resultados[id_teste] not in STATUS_COM_OBSERVACAO:
        st.session_state.observacoes[id_teste] = ""


def atualizar_observacao(id_teste):
    st.session_state.observacoes[id_teste] = st.session_state[f"obs_{id_teste}"]


def main():
    st.title("📋 Gerenciador de Casos de Teste")

    total_itens = min(len(CASOS_DE_TESTE), len(PASSOS_EXECUCAO))
    lista_ids = [f"TC-{str(i).zfill(3)}" for i in range(1, total_itens + 1)]

    dados_temporarios = {
        "ID": lista_ids,
        "Caso de Teste": CASOS_DE_TESTE[:total_itens],
        "Descrição / Passos": PASSOS_EXECUCAO[:total_itens]
    }
    df = pd.DataFrame(dados_temporarios)

    if "resultados" not in st.session_state:
        st.session_state.resultados = {id_t: "Não Executado" for id_t in lista_ids}
    if "observacoes" not in st.session_state:
        st.session_state.observacoes = {id_t: "" for id_t in lista_ids}

    valores_atuais = list(st.session_state.resultados.values())
    qtd_aprovado = valores_atuais.count("Aprovado ✅")
    qtd_reprovado = valores_atuais.count("Reprovado ❌")
    qtd_nao_aplic = valores_atuais.count("Não Aplicável ⚠️")
    qtd_nao_exec = valores_atuais.count("Não Executado")

    # --- SIDEBAR: RESUMO EXECUTIVO ---
    st.sidebar.markdown("## 📈 Resumo Executivo")

    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #f0f4f8; border-left: 5px solid #1a365d; margin-bottom: 10px;">
            <span style="font-size: 13px; color: #1a365d; font-weight: bold;">Total de Casos</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #0f172a;">{total_itens}</span>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #e6fffa; border-left: 5px solid #319795; margin-bottom: 10px;">
            <span style="font-size: 13px; color: #234e52; font-weight: bold;">Aprovado ✅</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #042f2e;">{qtd_aprovado}</span>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #fff5f5; border-left: 5px solid #e53e3e; margin-bottom: 10px;">
            <span style="font-size: 13px; color: #742a2a; font-weight: bold;">Reprovado ❌</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #451a1a;">{qtd_reprovado}</span>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #fffaf0; border-left: 5px solid #dd6b20; margin-bottom: 10px;">
            <span style="font-size: 13px; color: #7b341e; font-weight: bold;">Não Aplicável ⚠️</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #431407;">{qtd_nao_aplic}</span>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #edf2f7; border-left: 5px solid #4a5568; margin-bottom: 20px;">
            <span style="font-size: 13px; color: #2d3748; font-weight: bold;">Não Executados</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #1e293b;">{qtd_nao_exec}</span>
        </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR: EXPORTAR ---
    st.sidebar.markdown("### 💾 Exportar Resultados")
    try:
        pdf_bytes = gerar_pdf_fpdf(df, st.session_state.resultados, st.session_state.observacoes)
        st.sidebar.download_button(
            label="Baixar Relatório Execução (PDF)",
            data=pdf_bytes,
            file_name="relatorio_casos_de_teste.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar o PDF: {e}")

    # --- CONTEÚDO PRINCIPAL ---
    st.write(f"Exibindo os **{total_itens}** casos de teste cadastrados.")
    st.markdown("---")

    for index, row in df.iterrows():
        id_teste = row["ID"]
        num_teste = index + 1
        status_atual = st.session_state.resultados.get(id_teste, "Não Executado")
        obs_atual = st.session_state.observacoes.get(id_teste, "")

        if num_teste in MAPEAMENTO_SECOES:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='background-color: #1a365d; padding: 12px 15px; border-radius: 4px; margin-bottom: 20px; color: #ffffff; font-size: 18px; font-weight: bold; font-family: sans-serif;'>"
                f"{MAPEAMENTO_SECOES[num_teste]}"
                f"</div>",
                unsafe_allow_html=True
            )

        if status_atual == "Aprovado ✅":
            cor_fundo, cor_borda, cor_texto = "#e6fffa", "#319795", "#234e52"
        elif status_atual == "Reprovado ❌":
            cor_fundo, cor_borda, cor_texto = "#fff5f5", "#e53e3e", "#742a2a"
        elif status_atual == "Não Aplicável ⚠️":
            cor_fundo, cor_borda, cor_texto = "#fffaf0", "#dd6b20", "#7b341e"
        else:
            cor_fundo, cor_borda, cor_texto = "#f7fafc", "#cbd5e0", "#4a5568"

        with st.container():
            st.markdown(
                f"<div style='padding: 12px; border-radius: 6px; background-color: {cor_fundo}; border-left: 6px solid {cor_borda}; color: {cor_texto}; margin-bottom: 10px;'>"
                f"<h4 style='margin: 0; color: {cor_texto};'>🆔 {id_teste} — {row['Caso de Teste']}</h4>"
                f"<span style='font-size: 13px;'><b>Status Atual:</b> {status_atual}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

            st.write(f"**Passos para Execução:**\n{row['Descrição / Passos']}")

            st.selectbox(
                f"Alterar status de {id_teste}:",
                OPCOES_STATUS,
                index=OPCOES_STATUS.index(status_atual) if status_atual in OPCOES_STATUS else 0,
                key=f"status_{id_teste}",
                on_change=atualizar_status,
                args=(id_teste,)
            )

            # Campo de observação — só aparece para Reprovado e Não Aplicável
            if status_atual in STATUS_COM_OBSERVACAO:
                label_obs = "📝 Descrição do defeito / motivo:" if status_atual == "Reprovado ❌" else "📝 Motivo de não aplicabilidade:"
                st.text_area(
                    label_obs,
                    value=obs_atual,
                    key=f"obs_{id_teste}",
                    height=80,
                    placeholder="Descreva o defeito encontrado ou o motivo...",
                    on_change=atualizar_observacao,
                    args=(id_teste,)
                )

            st.markdown("---")


if __name__ == "__main__":
    main()