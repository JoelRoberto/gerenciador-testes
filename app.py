import json
import pandas as pd
import streamlit as st
from fpdf import FPDF
from pathlib import Path

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

CONFIG_PADRAO = {"org": "", "terminal": "", "sn": "", "so": "", "bundle": "", "qa": ""}

SAVES_DIR = Path("saves")
SAVES_DIR.mkdir(exist_ok=True)


# --- PERSISTÊNCIA ---

def _arquivo_save():
    qa = st.session_state.get("config", {}).get("qa", "").strip()
    nome = qa if qa else "anonimo"
    # Sanitiza para nome de arquivo seguro
    nome = "".join(c for c in nome if c.isalnum() or c in "-_").lower()
    nome = nome if nome else "anonimo"
    return SAVES_DIR / f"sessao_{nome}.json"


def salvar_sessao():
    dados = {
        "config": st.session_state.config,
        "resultados": st.session_state.resultados,
        "observacoes": st.session_state.observacoes,
    }
    _arquivo_save().write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar_sessao(qa_nome=""):
    """Tenta carregar save pelo nome do QA. Se não informado, retorna None."""
    if not qa_nome:
        return None, None, None
    nome = "".join(c for c in qa_nome.strip() if c.isalnum() or c in "-_").lower()
    arq = SAVES_DIR / f"sessao_{nome}.json"
    if arq.exists():
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
            return dados.get("config"), dados.get("resultados"), dados.get("observacoes")
        except Exception:
            pass
    return None, None, None


def limpar_sessao(lista_ids):
    arq = _arquivo_save()
    if arq.exists():
        arq.unlink()
    st.session_state.config = CONFIG_PADRAO.copy()
    st.session_state.resultados = {id_t: "Não Executado" for id_t in lista_ids}
    st.session_state.observacoes = {id_t: "" for id_t in lista_ids}
    st.session_state.config_aberta = True
    st.session_state.confirmar_reset = False


# --- PDF ---

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
    for orig, sub in substituicoes.items():
        texto = texto.replace(orig, sub)
    return texto.encode('latin-1', 'ignore').decode('latin-1')


def gerar_pdf_fpdf(df_base, resultados, observacoes, config):
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

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 8, "Identificacao da Rodada:", ln=True)
    pdf.ln(2)

    campos_config = [
        ("ORG", config.get("org", "")),
        ("Terminal", config.get("terminal", "")),
        ("SN", config.get("sn", "")),
        ("SO", config.get("so", "")),
        ("Bundle", config.get("bundle", "")),
        ("QA Responsavel", config.get("qa", "")),
    ]

    w_label, w_valor, gap = 32, 62, 4
    pares = [(campos_config[i], campos_config[i+3]) for i in range(3)]

    for (label_a, valor_a), (label_b, valor_b) in pares:
        pdf.set_fill_color(43, 108, 176)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w_label, 8, f" {label_a}", border=1, fill=True)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_text_color(45, 55, 72)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(w_valor, 8, f" {tratar_texto_pdf(valor_a)}", border=1, fill=True)
        pdf.cell(gap, 8, "", border=0)
        pdf.set_fill_color(43, 108, 176)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w_label, 8, f" {label_b}", border=1, fill=True)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_text_color(45, 55, 72)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(w_valor, 8, f" {tratar_texto_pdf(valor_b)}", border=1, fill=True, ln=True)

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 8, "Resumo Executivo da Rodada:", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(45, 55, 72)
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
        status_limpo = status_original.replace(" ✅", "").replace(" ❌", "").replace(" ⚠️", "")
        caso_limpo = tratar_texto_pdf(row["Caso de Teste"])
        passos_limpo = tratar_texto_pdf(row["Descrição / Passos"])
        obs_raw = str(row["Observacao"]).strip() if row["Observacao"] else ""
        obs_limpo = tratar_texto_pdf(obs_raw) if obs_raw else ""

        linhas_caso = len(pdf.multi_cell(w_caso - 4, h_linha_texto, caso_limpo, split_only=True))
        linhas_passos = len(pdf.multi_cell(w_passos - 4, h_linha_texto, passos_limpo, split_only=True))
        max_linhas = max(linhas_caso, linhas_passos, 1)
        altura_linha_principal = (max_linhas * h_linha_texto) + 6

        obs_label = "Observacao: "
        linhas_obs = len(pdf.multi_cell(largura_total - 6, h_linha_texto, obs_label + obs_limpo, split_only=True)) if obs_limpo else 0
        altura_obs = (linhas_obs * h_linha_texto) + 4 if obs_limpo else 0

        if pdf.get_y() + altura_linha_principal + altura_obs > 275:
            pdf.add_page()

        x, y = pdf.get_x(), pdf.get_y()

        pdf.rect(x, y, w_id, altura_linha_principal)
        pdf.rect(x + w_id, y, w_caso, altura_linha_principal)
        pdf.rect(x + w_id + w_caso, y, w_passos, altura_linha_principal)

        if "Aprovado" in status_original:
            pdf.set_fill_color(230, 255, 250); pdf.set_text_color(35, 78, 82)
        elif "Reprovado" in status_original:
            pdf.set_fill_color(255, 245, 245); pdf.set_text_color(116, 42, 42)
        elif "Não Aplicável" in status_original:
            pdf.set_fill_color(255, 250, 240); pdf.set_text_color(123, 52, 30)
        else:
            pdf.set_fill_color(247, 250, 252); pdf.set_text_color(74, 85, 104)

        pdf.rect(x + w_id + w_caso + w_passos, y, w_status, altura_linha_principal, style="F")
        pdf.rect(x + w_id + w_caso + w_passos, y, w_status, altura_linha_principal)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(43, 108, 176)
        pdf.set_xy(x, y + (altura_linha_principal / 2) - 2)
        pdf.cell(w_id, 4, str(row["ID"]), align="C")

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(45, 55, 72)
        pdf.set_xy(x + w_id + 2, y + 3)
        pdf.multi_cell(w_caso - 4, h_linha_texto, caso_limpo)

        pdf.set_xy(x + w_id + w_caso + 2, y + 3)
        pdf.multi_cell(w_passos - 4, h_linha_texto, passos_limpo)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(x + w_id + w_caso + w_passos, y + (altura_linha_principal / 2) - 2)
        pdf.cell(w_status, 4, status_limpo, align="C")

        y_obs = y + altura_linha_principal
        if obs_limpo:
            if "Reprovado" in status_original:
                pdf.set_fill_color(255, 235, 235); pdf.set_text_color(116, 42, 42)
            else:
                pdf.set_fill_color(255, 244, 225); pdf.set_text_color(123, 52, 30)
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


# --- CALLBACKS ---

def atualizar_status(id_teste):
    st.session_state.resultados[id_teste] = st.session_state[f"status_{id_teste}"]
    if st.session_state.resultados[id_teste] not in STATUS_COM_OBSERVACAO:
        st.session_state.observacoes[id_teste] = ""
    salvar_sessao()  # auto-save


def atualizar_observacao(id_teste):
    st.session_state.observacoes[id_teste] = st.session_state[f"obs_{id_teste}"]
    salvar_sessao()  # auto-save


def salvar_config():
    st.session_state.config = {
        "org": st.session_state.cfg_org,
        "terminal": st.session_state.cfg_terminal,
        "sn": st.session_state.cfg_sn,
        "so": st.session_state.cfg_so,
        "bundle": st.session_state.cfg_bundle,
        "qa": st.session_state.cfg_qa,
    }
    st.session_state.config_aberta = False
    # Tenta carregar save existente deste usuário
    qa = st.session_state.config.get("qa", "").strip()
    config_salva, resultados_salvos, observacoes_salvas = carregar_sessao(qa)
    if resultados_salvos:
        st.session_state.resultados = resultados_salvos
        st.session_state.observacoes = observacoes_salvas
    salvar_sessao()  # cria/atualiza arquivo do usuário


# --- FORM CONFIG ---

def renderizar_form_config():
    st.markdown("## ⚙️ Configuração da Rodada de Testes")
    st.markdown("Preencha as informações abaixo. Todos os campos são opcionais.")
    st.markdown("---")

    cfg = st.session_state.config
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("🏢 ORG", ["", "STONE", "TON"],
                     index=["", "STONE", "TON"].index(cfg.get("org", "")) if cfg.get("org", "") in ["", "STONE", "TON"] else 0,
                     key="cfg_org")
        st.text_input("🔢 SN (Serial Number)", value=cfg.get("sn", ""), key="cfg_sn")
        st.text_input("📦 BUNDLE", value=cfg.get("bundle", ""), key="cfg_bundle")
    with col2:
        st.selectbox("🖥️ TERMINAL", ["", "P2-B", "P2A11"],
                     index=["", "P2-B", "P2A11"].index(cfg.get("terminal", "")) if cfg.get("terminal", "") in ["", "P2-B", "P2A11"] else 0,
                     key="cfg_terminal")
        st.text_input("💻 SO (Sistema Operacional)", value=cfg.get("so", ""), key="cfg_so")
        st.text_input("👤 QA Responsável", value=cfg.get("qa", ""), key="cfg_qa")

    st.markdown("---")
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        st.button("✅ Salvar e Continuar", on_click=salvar_config, type="primary")


# --- MAIN ---

def main():
    total_itens = min(len(CASOS_DE_TESTE), len(PASSOS_EXECUCAO))
    lista_ids = [f"TC-{str(i).zfill(3)}" for i in range(1, total_itens + 1)]

    # Inicializa session_state — sempre abre config na primeira vez
    if "resultados" not in st.session_state:
        st.session_state.config = CONFIG_PADRAO.copy()
        st.session_state.resultados = {id_t: "Não Executado" for id_t in lista_ids}
        st.session_state.observacoes = {id_t: "" for id_t in lista_ids}
        st.session_state.config_aberta = True

    if "config_aberta" not in st.session_state:
        st.session_state.config_aberta = False
    for _k, _v in [("tc_capturando", None), ("_adb_proc", None),
                   ("adb_packages", []), ("adb_device", None),
                   ("log_arquivo_atual", ""), ("confirmar_reset", False)]:
        if _k not in st.session_state:
            st.session_state[_k] = _v
    if "confirmar_reset" not in st.session_state:
        st.session_state.confirmar_reset = False

    df = pd.DataFrame({
        "ID": lista_ids,
        "Caso de Teste": CASOS_DE_TESTE[:total_itens],
        "Descrição / Passos": PASSOS_EXECUCAO[:total_itens]
    })

    # Tela de configuração
    if st.session_state.config_aberta:
        renderizar_form_config()
        return

    # --- SIDEBAR ---
    valores_atuais = list(st.session_state.resultados.values())
    qtd_aprovado = valores_atuais.count("Aprovado ✅")
    qtd_reprovado = valores_atuais.count("Reprovado ❌")
    qtd_nao_aplic = valores_atuais.count("Não Aplicável ⚠️")
    qtd_nao_exec = valores_atuais.count("Não Executado")
    cfg = st.session_state.config

    st.sidebar.markdown("## 🗂️ Dados da Rodada")
    for label, valor in [("ORG", cfg.get("org","")), ("Terminal", cfg.get("terminal","")),
                         ("SN", cfg.get("sn","")), ("SO", cfg.get("so","")),
                         ("Bundle", cfg.get("bundle","")), ("QA", cfg.get("qa",""))]:
        st.sidebar.markdown(f"**{label}:** {valor if valor else '—'}")

    if st.sidebar.button("✏️ Editar Configuração"):
        st.session_state.config_aberta = True
        st.rerun()

    st.sidebar.markdown("---")

    # --- SALVAR / RESETAR ---
    st.sidebar.markdown("### 💾 Sessão")

    if st.sidebar.button("💾 Salvar Progresso", use_container_width=True):
        salvar_sessao()
        st.sidebar.success("Salvo!")

    # Botão iniciar do zero com confirmação
    if not st.session_state.confirmar_reset:
        if st.sidebar.button("🔄 Iniciar do Zero", use_container_width=True):
            st.session_state.confirmar_reset = True
            st.rerun()
    else:
        st.sidebar.warning("⚠️ Isso apagará todo o progresso atual. Confirma?")
        col_sim, col_nao = st.sidebar.columns(2)
        with col_sim:
            if st.button("✅ Sim", use_container_width=True):
                limpar_sessao(lista_ids)
                st.rerun()
        with col_nao:
            if st.button("❌ Não", use_container_width=True):
                st.session_state.confirmar_reset = False
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📱 Captura de Log (ADB)")

    if st.sidebar.button("🔄 Detectar Dispositivo", use_container_width=True):
        st.rerun()

    _dispositivos = listar_dispositivos()
    if not _dispositivos:
        st.sidebar.warning("Nenhum dispositivo USB encontrado.")
        st.sidebar.caption("Verifique o cabo e reinicie o Streamlit com ADB no PATH.")
        adb_ativo = False
    else:
        _dev = st.sidebar.selectbox("Dispositivo:", _dispositivos, key="adb_device_sel")
        st.session_state.adb_device = _dev
        if st.sidebar.button("🔍 Buscar apps Stone/Ton", use_container_width=True):
            with st.spinner("Buscando..."):
                st.session_state.adb_packages = listar_packages_stone(_dev)
        if st.session_state.adb_packages:
            st.sidebar.success(f"✅ {len(st.session_state.adb_packages)} packages prontos")
            adb_ativo = True
        else:
            st.sidebar.caption("Clique em 'Buscar apps Stone/Ton'.")
            adb_ativo = False

    if st.session_state.tc_capturando:
        _arq = Path(st.session_state.get("log_arquivo_atual", ""))
        _kb = _arq.stat().st_size / 1024 if _arq.exists() else 0
        st.sidebar.info(f"🔴 Capturando **{st.session_state.tc_capturando}** — {_kb:.1f} KB")
        if st.sidebar.button("⏹️ Parar Captura", use_container_width=True):
            parar_captura(); st.rerun()

    st.sidebar.markdown("### 📁 Logs Salvos")
    _logs = sorted(LOG_DIR.glob("*.txt"), reverse=True)
    if not _logs:
        st.sidebar.caption("Nenhum log capturado ainda.")
    else:
        for _arq in _logs:
            _kb = _arq.stat().st_size / 1024
            st.sidebar.markdown(f"📄 `{_arq.name[:28]}` — {_kb:.1f} KB")
            _c1, _c2 = st.sidebar.columns(2)
            with _c1:
                with open(_arq, "rb") as _f:
                    st.sidebar.download_button("⬇️ Baixar", data=_f.read(),
                        file_name=_arq.name, mime="text/plain", key=f"dl_{_arq.name}")
            with _c2:
                if st.sidebar.button("🗑️ Excluir", key=f"del_{_arq.name}"):
                    _arq.unlink(); st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📈 Resumo Executivo")

    for _bg, _bd, _tit, _val, _ct in [
        ("#f0f4f8","#1a365d","Total de Casos", total_itens, "#0f172a"),
        ("#e6fffa","#319795","Aprovado ✅", qtd_aprovado, "#042f2e"),
        ("#fff5f5","#e53e3e","Reprovado ❌", qtd_reprovado, "#451a1a"),
        ("#fffaf0","#dd6b20","Não Aplicável ⚠️", qtd_nao_aplic, "#431407"),
        ("#edf2f7","#4a5568","Não Executados", qtd_nao_exec, "#1e293b"),
    ]:
        st.sidebar.markdown(f"""
            <div style="padding:10px;border-radius:6px;background-color:{_bg};border-left:5px solid {_bd};margin-bottom:10px;">
                <span style="font-size:13px;color:{_bd};font-weight:bold;">{_tit}</span><br>
                <span style="font-size:20px;font-weight:bold;color:{_ct};">{_val}</span>
            </div>
        """, unsafe_allow_html=True)

    st.sidebar.markdown("### 📄 Exportar")
    try:
        pdf_bytes = gerar_pdf_fpdf(df, st.session_state.resultados, st.session_state.observacoes, cfg)
        st.sidebar.download_button(
            label="Baixar Relatório (PDF)",
            data=pdf_bytes,
            file_name="relatorio_casos_de_teste.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar PDF: {e}")

    # --- CONTEÚDO PRINCIPAL ---
    st.title("📋 Gerenciador de Casos de Teste")
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
                f"{MAPEAMENTO_SECOES[num_teste]}</div>",
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

            _col_sel, _col_adb = st.columns([4, 1])
            with _col_sel:
                st.selectbox(
                    f"Alterar status de {id_teste}:",
                    OPCOES_STATUS,
                    index=OPCOES_STATUS.index(status_atual) if status_atual in OPCOES_STATUS else 0,
                    key=f"status_{id_teste}",
                    on_change=atualizar_status,
                    args=(id_teste,)
                )
            with _col_adb:
                if adb_ativo:
                    _tc_cap = st.session_state.tc_capturando
                    if _tc_cap == id_teste:
                        _arq = Path(st.session_state.get("log_arquivo_atual", ""))
                        _kb = _arq.stat().st_size / 1024 if _arq.exists() else 0
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button(f"⏹️ {_kb:.0f}KB", key=f"adb_{id_teste}", use_container_width=True):
                            parar_captura(); st.rerun()
                    elif _tc_cap is None:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("▶️ Log", key=f"adb_{id_teste}", use_container_width=True):
                            _ok = iniciar_captura_tc(id_teste,
                                                     st.session_state.adb_device,
                                                     st.session_state.adb_packages)
                            if not _ok:
                                st.warning("Nenhum processo stone ativo. Abra o app no POS.")
                            st.rerun()
                    else:
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.button("▶️ Log", key=f"adb_{id_teste}", disabled=True, use_container_width=True)

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