import pandas as pd
import streamlit as st
from fpdf import FPDF

st.set_page_config(page_title="Gerenciador de Casos de Teste", layout="wide")

# Bloco seguro para importar as listas do dados.py
try:
    from dados import CASOS_DE_TESTE, PASSOS_EXECUCAO
except Exception as e:
    st.error(f"❌ Erro ao carregar o arquivo dados.py: {e}")
    st.stop()

# Dicionário mapeando o ID inicial de cada seção (apenas para o Dashboard)
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
    texto = texto.replace("✅", "[Passou]").replace("❌", "[Falhou]").replace("⚠️", "[Bloqueado]").replace("⚡", "")
    
    substituicoes = {
        "á": "a", "à": "a", "ã": "a", "â": "a", "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "é": "e", "è": "e", "ê": "e", "É": "E", "È": "E", "Ê": "E",
        "í": "i", "ì": "i", "î": "i", "Í": "I", "Ì": "I", "Î": "I",
        "ó": "o", "ò": "o", "ô": "o", "õ": "o", "Ó": "O", "Ò": "O", "Ô": "O", "Õ": "O",
        "ú": "u", "ù": "u", "û": "u", "Ú": "U", "Ù": "U", "Û": "U",
        "ç": "c", "Ç": "C", "º": ".", "ª": ".", "–": "-", "—": "-",
        "’": "'", "‘": "'", "“": '"', "”": '"'
    }
    for original, substitute in substituicoes.items():
        texto = texto.replace(original, substitute)
        
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def gerar_pdf_fpdf(df_base, resultados):
    df = df_base.copy()
    df["Resultado"] = df["ID"].map(lambda x: resultados.get(x, "Não Executado"))
    
    qtd_total = len(df)
    qtd_passou = len(df[df["Resultado"] == "Passou ✅"])
    qtd_falhou = len(df[df["Resultado"] == "Falhou ❌"])
    qtd_bloqueado = len(df[df["Resultado"] == "Bloqueado ⚠️"])
    qtd_nao_exec = qtd_total - (qtd_passou + qtd_falhou + qtd_bloqueado)

    pdf = RelatorioPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 8, "Resumo Executivo da Rodada:", ln=True)
    pdf.ln(2)
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(240, 244, 248)
    pdf.cell(35, 10, f" Total: {qtd_total}", border=1, fill=True)
    pdf.set_fill_color(230, 255, 250)
    pdf.cell(38, 10, f" Passou: {qtd_passou}", border=1, fill=True)
    pdf.set_fill_color(255, 245, 245)
    pdf.cell(38, 10, f" Falhou: {qtd_falhou}", border=1, fill=True)
    pdf.set_fill_color(255, 250, 240)
    pdf.cell(38, 10, f" Bloqueado: {qtd_bloqueado}", border=1, fill=True)
    pdf.set_fill_color(247, 250, 252)
    pdf.cell(41, 10, f" Nao Exec.: {qtd_nao_exec}", border=1, fill=True, ln=True)
    
    pdf.ln(8)
    
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(43, 108, 176)
    pdf.set_text_color(255, 255, 255)
    
    w_id, w_caso, w_passos, w_status = 18, 54, 93, 25
    pdf.cell(w_id, 10, "ID", border=1, fill=True, align="C")
    pdf.cell(w_caso, 10, " Caso de Teste", border=1, fill=True)
    pdf.cell(w_passos, 10, " Passos de Execucao", border=1, fill=True)
    pdf.cell(w_status, 10, "Resultado", border=1, fill=True, ln=True, align="C")
    
    h_linha_texto = 4.5
    
    for idx, row in df.iterrows():
        status_original = str(row["Resultado"])
        status_limpo = status_original.replace(" ✅", "").replace(" ❌", "").replace(" ⚠️", "")
        
        caso_limpo = tratar_texto_pdf(row["Caso de Teste"])
        passos_limpo = tratar_texto_pdf(row["Descrição / Passos"])
        
        linhas_caso = len(pdf.multi_cell(w_caso - 4, h_linha_texto, caso_limpo, split_only=True))
        linhas_passos = len(pdf.multi_cell(w_passos - 4, h_linha_texto, passos_limpo, split_only=True))
        
        max_linhas = max(linhas_caso, max_linhas, 1) if 'max_linhas' in locals() else max(linhas_caso, linhas_passos, 1)
        max_linhas = max(linhas_caso, linhas_passos, 1)
        altura_dinamica_linha = (max_linhas * h_linha_texto) + 6
        
        if pdf.get_y() + altura_dinamica_linha > 275:
            pdf.add_page()
            
        x, y = pdf.get_x(), pdf.get_y()
        
        pdf.rect(x, y, w_id, altura_dinamica_linha)
        pdf.rect(x + w_id, y, w_caso, altura_dinamica_linha)
        pdf.rect(x + w_id + w_caso, y, w_passos, altura_dinamica_linha)
        
        if "Passou" in status_original:
            pdf.set_fill_color(230, 255, 250)
            pdf.set_text_color(35, 78, 82)
        elif "Falhou" in status_original:
            pdf.set_fill_color(255, 245, 245)
            pdf.set_text_color(116, 42, 42)
        elif "Bloqueado" in status_original:
            pdf.set_fill_color(255, 250, 240)
            pdf.set_text_color(123, 52, 30)
        else:
            pdf.set_fill_color(247, 250, 252)
            pdf.set_text_color(74, 85, 104)
            
        pdf.rect(x + w_id + w_caso + w_passos, y, w_status, altura_dinamica_linha, style="F")
        pdf.rect(x + w_id + w_caso + w_passos, y, w_status, altura_dinamica_linha)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(43, 108, 176)
        pdf.set_xy(x, y + (altura_dinamica_linha / 2) - 2)
        pdf.cell(w_id, 4, str(row["ID"]), align="C")
        
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(45, 55, 72)
        pdf.set_xy(x + w_id + 2, y + 3)
        pdf.multi_cell(w_caso - 4, h_linha_texto, caso_limpo)
        
        pdf.set_xy(x + w_id + w_caso + 2, y + 3)
        pdf.multi_cell(w_passos - 4, h_linha_texto, passos_limpo)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(x + w_id + w_caso + w_passos, y + (altura_dinamica_linha / 2) - 2)
        pdf.cell(w_status, 4, status_limpo, align="C")
        
        pdf.set_xy(10, y + altura_dinamica_linha)
        
    return bytes(pdf.output())

def atualizar_status(id_teste):
    st.session_state.resultados[id_teste] = st.session_state[f"status_{id_teste}"]

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

    valores_atuais = list(st.session_state.resultados.values())
    qtd_passou = valores_atuais.count("Passou ✅")
    qtd_falhou = valores_atuais.count("Falhou ❌")
    qtd_bloqueado = valores_atuais.count("Bloqueado ⚠️")
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
            <span style="font-size: 13px; color: #234e52; font-weight: bold;">Passou ✅</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #042f2e;">{qtd_passou}</span>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #fff5f5; border-left: 5px solid #e53e3e; margin-bottom: 10px;">
            <span style="font-size: 13px; color: #742a2a; font-weight: bold;">Falhou ❌</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #451a1a;">{qtd_falhou}</span>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #fffaf0; border-left: 5px solid #dd6b20; margin-bottom: 10px;">
            <span style="font-size: 13px; color: #7b341e; font-weight: bold;">Bloqueado ⚠️</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #431407;">{qtd_bloqueado}</span>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
        <div style="padding: 10px; border-radius: 6px; background-color: #edf2f7; border-left: 5px solid #4a5568; margin-bottom: 20px;">
            <span style="font-size: 13px; color: #2d3748; font-weight: bold;">Não Executados</span><br>
            <span style="font-size: 20px; font-weight: bold; color: #1e293b;">{qtd_nao_exec}</span>
        </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR: EXPORTAR RESULTADOS ---
    st.sidebar.markdown("### 💾 Exportar Resultados")
    try:
        pdf_bytes = gerar_pdf_fpdf(df, st.session_state.resultados)
        st.sidebar.download_button(
            label="Baixar Relatório Execução (PDF)",
            data=pdf_bytes,
            file_name="relatorio_casos_de_teste.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar o PDF: {e}")

    # --- CONTEÚDO PRINCIPAL (DASHBOARD) ---
    st.write(f"Exibindo os **{total_itens}** casos de teste cadastrados.")
    st.markdown("---")

    for index, row in df.iterrows():
        id_teste = row["ID"]
        num_teste = index + 1
        status_atual = st.session_state.resultados.get(id_teste, "Não Executado")
        
        if num_teste in MAPEAMENTO_SECOES:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='background-color: #1a365d; padding: 12px 15px; border-radius: 4px; margin-bottom: 20px; color: #ffffff; font-size: 18px; font-weight: bold; font-family: sans-serif;'>"
                f"{MAPEAMENTO_SECOES[num_teste]}"
                f"</div>", 
                unsafe_allow_html=True
            )

        if status_atual == "Passou ✅":
            cor_fundo, col_borda, cor_texto = "#e6fffa", "#319795", "#234e52"
        elif status_atual == "Falhou ❌":
            cor_fundo, col_borda, cor_texto = "#fff5f5", "#e53e3e", "#742a2a"
        elif status_atual == "Bloqueado ⚠️":
            cor_fundo, col_borda, cor_texto = "#fffaf0", "#dd6b20", "#7b341e"
        else:
            cor_fundo, col_borda, cor_texto = "#f7fafc", "#cbd5e0", "#4a5568"

        with st.container():
            st.markdown(
                f"<div style='padding: 12px; border-radius: 6px; background-color: {cor_fundo}; border-left: 6px solid {col_borda}; color: {cor_texto}; margin-bottom: 10px;'>"
                f"<h4 style='margin: 0; color: {cor_texto};'>🆔 {id_teste} — {row['Caso de Teste']}</h4>"
                f"<span style='font-size: 13px;'><b>Status Atual:</b> {status_atual}</span>"
                f"</div>", 
                unsafe_allow_html=True
            )
            
            st.write(f"**Passos para Execução:**\n{row['Descrição / Passos']}")
            
            opcoes_status = ["Não Executado", "Passou ✅", "Falhou ❌", "Bloqueado ⚠️"]
            
            st.selectbox(
                f"Alterar status de {id_teste}:", 
                opcoes_status, 
                index=opcoes_status.index(status_atual) if status_atual in opcoes_status else 0, 
                key=f"status_{id_teste}",
                on_change=atualizar_status,
                args=(id_teste,)
            )
            st.markdown("---")

if __name__ == "__main__":
    main()