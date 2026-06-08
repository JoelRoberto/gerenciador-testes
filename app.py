import json
import subprocess
import threading
import datetime
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
    1: "🚀 SEÇÃO LAUNCHER", 10: "💳 SEÇÃO PAGAMENTO", 61: "❌ SEÇÃO CANCELAMENTO",
    72: "🔌 SEÇÃO CONEXÃO", 87: "🔓 SEÇÃO ATIVAÇÃO", 98: "⚙️ SEÇÃO AJUSTES",
    114: "❓ SEÇÃO AJUDA", 122: "🧮 SEÇÃO CALCULADORA", 125: "📊 SEÇÃO SIMULADOR DE VENDAS",
    133: "🧾 SEÇÃO REIMPRESSÃO / RECIBOS", 142: "📈 SEÇÃO RELATÓRIO",
    151: "🔒 SEÇÃO FECHAMENTO", 157: "🏪 SEÇÃO LOJA", 162: "✨ SEÇÃO NOVIDADES"
}

OPCOES_STATUS = ["Não Executado", "Aprovado ✅", "Reprovado ❌", "Não Aplicável ⚠️"]
STATUS_COM_OBSERVACAO = {"Reprovado ❌", "Não Aplicável ⚠️"}
CONFIG_PADRAO = {"org": "", "terminal": "", "sn": "", "so": "", "bundle": "", "qa": ""}

SAVES_DIR = Path("saves")
LOG_DIR = Path("logs")
SAVES_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


# ── PERSISTÊNCIA ──────────────────────────────────────────────────────────────

def _arquivo_save():
    qa = st.session_state.get("config", {}).get("qa", "").strip()
    nome = "".join(c for c in (qa or "anonimo") if c.isalnum() or c in "-_").lower()
    return SAVES_DIR / f"sessao_{nome or 'anonimo'}.json"


def salvar_sessao():
    dados = {
        "config": st.session_state.config,
        "resultados": st.session_state.resultados,
        "observacoes": st.session_state.observacoes,
    }
    _arquivo_save().write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar_sessao(qa_nome=""):
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


# ── ADB ───────────────────────────────────────────────────────────────────────

def adb(args, timeout=10):
    try:
        r = subprocess.run(["adb"] + args, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return "", "ADB não encontrado"
    except subprocess.TimeoutExpired:
        return "", "Timeout"


def listar_dispositivos():
    stdout, _ = adb(["devices"])
    return [l.split("\t")[0].strip() for l in stdout.splitlines()[1:] if "\tdevice" in l]


def listar_packages_stone(device_id):
    stdout, _ = adb(["-s", device_id, "shell", "pm", "list", "packages"])
    return sorted(l.replace("package:", "").strip() for l in stdout.splitlines()
                  if "stone" in l.lower() or "ton" in l.lower())


def get_pids_stone(device_id, packages):
    """Retorna dict {package: pid} para todos os packages stone em execução."""
    stdout, _ = adb(["-s", device_id, "shell", "ps", "-A"])
    pids = {}
    for linha in stdout.splitlines():
        for pkg in packages:
            if pkg in linha:
                partes = linha.split()
                if len(partes) >= 2:
                    try:
                        pids[pkg] = partes[1]
                    except Exception:
                        pass
    return pids


def capturar_log_thread(device_id, packages, tc, nome_arquivo, pids):
    """Thread de captura — filtra por todos os PIDs stone simultaneamente."""
    sentinela = LOG_DIR / ".parar"
    if sentinela.exists():
        sentinela.unlink()

    cmd = ["adb", "-s", device_id, "logcat", "-v", "threadtime"]
    pid_set = set(pids.values())

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        st.session_state._adb_proc = proc

        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write("=== LOG CAPTURADO ===\n")
            f.write(f"TC: {tc}\n")
            f.write(f"Device: {device_id}\n")
            f.write(f"Packages monitorados:\n")
            for pkg, pid in pids.items():
                f.write(f"  {pkg} (PID {pid})\n")
            f.write(f"Inicio: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")

            for linha in proc.stdout:
                if sentinela.exists():
                    break
                partes = linha.split()
                # formato threadtime: DATA HORA PID TID LEVEL TAG: msg
                if len(partes) >= 3 and partes[2] in pid_set:
                    f.write(linha)
                    f.flush()
                # também inclui qualquer linha que mencione algum package stone
                elif any(pkg in linha for pkg in packages):
                    f.write(linha)
                    f.flush()
    except Exception as e:
        with open(nome_arquivo, "a", encoding="utf-8") as f:
            f.write(f"\n[ERRO: {e}]\n")


def iniciar_captura_tc(tc, device_id, packages):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = LOG_DIR / f"{tc}_stone_{timestamp}.txt"

    pids = get_pids_stone(device_id, packages)
    if not pids:
        st.warning("⚠️ Nenhum processo stone encontrado. Abra o app no POS antes de capturar.")
        return

    st.session_state.tc_capturando = tc
    st.session_state.log_arquivo_atual = str(nome_arquivo)

    thread = threading.Thread(
        target=capturar_log_thread,
        args=(device_id, packages, tc, nome_arquivo, pids),
        daemon=True
    )
    thread.start()


def parar_captura():
    (LOG_DIR / ".parar").touch()
    st.session_state.tc_capturando = None
    proc = st.session_state.get("_adb_proc")
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass
    st.session_state._adb_proc = None


# ── PDF ───────────────────────────────────────────────────────────────────────

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
    texto = (str(texto)
             .replace("✅", "[Aprovado]").replace("❌", "[Reprovado]")
             .replace("⚠️", "[Nao Aplicavel]").replace("⚡", ""))
    subs = {
        "á":"a","à":"a","ã":"a","â":"a","Á":"A","À":"A","Ã":"A","Â":"A",
        "é":"e","è":"e","ê":"e","É":"E","È":"E","Ê":"E",
        "í":"i","ì":"i","î":"i","Í":"I","Ì":"I","Î":"I",
        "ó":"o","ò":"o","ô":"o","õ":"o","Ó":"O","Ò":"O","Ô":"O","Õ":"O",
        "ú":"u","ù":"u","û":"u","Ú":"U","Ù":"U","Û":"U",
        "ç":"c","Ç":"C","º":".","ª":".","–":"-","—":"-",
        "\u2018":"'","\u2019":"'","\u201c":'"',"\u201d":'"'
    }
    for o, s in subs.items():
        texto = texto.replace(o, s)
    return texto.encode("latin-1", "ignore").decode("latin-1")


def gerar_pdf_fpdf(df_base, resultados, observacoes, config):
    df = df_base.copy()
    df["Resultado"] = df["ID"].map(lambda x: resultados.get(x, "Não Executado"))
    df["Observacao"] = df["ID"].map(lambda x: observacoes.get(x, ""))

    qtd_total = len(df)
    qtd_ap = len(df[df["Resultado"] == "Aprovado ✅"])
    qtd_rp = len(df[df["Resultado"] == "Reprovado ❌"])
    qtd_na = len(df[df["Resultado"] == "Não Aplicável ⚠️"])
    qtd_ne = qtd_total - (qtd_ap + qtd_rp + qtd_na)

    pdf = RelatorioPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Ficha de identificação
    pdf.set_font("Helvetica", "B", 11); pdf.set_text_color(45, 55, 72)
    pdf.cell(0, 8, "Identificacao da Rodada:", ln=True); pdf.ln(2)
    campos = [("ORG", config.get("org","")), ("Terminal", config.get("terminal","")),
              ("SN", config.get("sn","")), ("SO", config.get("so","")),
              ("Bundle", config.get("bundle","")), ("QA Responsavel", config.get("qa",""))]
    w_l, w_v, gap = 32, 62, 4
    for (la, va), (lb, vb) in [(campos[i], campos[i+3]) for i in range(3)]:
        pdf.set_fill_color(43,108,176); pdf.set_text_color(255,255,255)
        pdf.set_font("Helvetica","B",8); pdf.cell(w_l,8,f" {la}",border=1,fill=True)
        pdf.set_fill_color(248,250,252); pdf.set_text_color(45,55,72)
        pdf.set_font("Helvetica","",9); pdf.cell(w_v,8,f" {tratar_texto_pdf(va)}",border=1,fill=True)
        pdf.cell(gap,8,"",border=0)
        pdf.set_fill_color(43,108,176); pdf.set_text_color(255,255,255)
        pdf.set_font("Helvetica","B",8); pdf.cell(w_l,8,f" {lb}",border=1,fill=True)
        pdf.set_fill_color(248,250,252); pdf.set_text_color(45,55,72)
        pdf.set_font("Helvetica","",9); pdf.cell(w_v,8,f" {tratar_texto_pdf(vb)}",border=1,fill=True,ln=True)
    pdf.ln(6)

    # Resumo
    pdf.set_font("Helvetica","B",11); pdf.set_text_color(45,55,72)
    pdf.cell(0,8,"Resumo Executivo da Rodada:",ln=True); pdf.ln(2)
    pdf.set_font("Helvetica","",9); pdf.set_text_color(45,55,72)
    for cor, txt in [((240,244,248),f" Total: {qtd_total}"),((230,255,250),f" Aprovado: {qtd_ap}"),
                     ((255,245,245),f" Reprovado: {qtd_rp}"),((255,250,240),f" Nao Aplic.: {qtd_na}"),
                     ((247,250,252),f" Nao Exec.: {qtd_ne}")]:
        pdf.set_fill_color(*cor); pdf.cell(38,10,txt,border=1,fill=True)
    pdf.ln(True); pdf.ln(8)

    # Tabela
    w_id,w_caso,w_passos,w_status = 18,54,93,25
    lt = w_id+w_caso+w_passos+w_status
    pdf.set_font("Helvetica","B",10); pdf.set_fill_color(43,108,176); pdf.set_text_color(255,255,255)
    pdf.cell(w_id,10,"ID",border=1,fill=True,align="C")
    pdf.cell(w_caso,10," Caso de Teste",border=1,fill=True)
    pdf.cell(w_passos,10," Passos de Execucao",border=1,fill=True)
    pdf.cell(w_status,10,"Resultado",border=1,fill=True,ln=True,align="C")
    h = 4.5

    for _, row in df.iterrows():
        so = str(row["Resultado"])
        sl = so.replace(" ✅","").replace(" ❌","").replace(" ⚠️","")
        cl = tratar_texto_pdf(row["Caso de Teste"])
        pl = tratar_texto_pdf(row["Descrição / Passos"])
        ob = tratar_texto_pdf(str(row["Observacao"]).strip()) if row["Observacao"] else ""
        lc = len(pdf.multi_cell(w_caso-4,h,cl,split_only=True))
        lp = len(pdf.multi_cell(w_passos-4,h,pl,split_only=True))
        alp = (max(lc,lp,1)*h)+6
        ol = "Observacao: "
        ao = ((len(pdf.multi_cell(lt-6,h,ol+ob,split_only=True))*h)+4) if ob else 0
        if pdf.get_y()+alp+ao > 275:
            pdf.add_page()
        x,y = pdf.get_x(),pdf.get_y()
        pdf.rect(x,y,w_id,alp); pdf.rect(x+w_id,y,w_caso,alp); pdf.rect(x+w_id+w_caso,y,w_passos,alp)
        if "Aprovado" in so: pdf.set_fill_color(230,255,250); pdf.set_text_color(35,78,82)
        elif "Reprovado" in so: pdf.set_fill_color(255,245,245); pdf.set_text_color(116,42,42)
        elif "Não Aplicável" in so: pdf.set_fill_color(255,250,240); pdf.set_text_color(123,52,30)
        else: pdf.set_fill_color(247,250,252); pdf.set_text_color(74,85,104)
        pdf.rect(x+w_id+w_caso+w_passos,y,w_status,alp,style="F")
        pdf.rect(x+w_id+w_caso+w_passos,y,w_status,alp)
        pdf.set_font("Helvetica","B",9); pdf.set_text_color(43,108,176)
        pdf.set_xy(x,y+(alp/2)-2); pdf.cell(w_id,4,str(row["ID"]),align="C")
        pdf.set_font("Helvetica","",8.5); pdf.set_text_color(45,55,72)
        pdf.set_xy(x+w_id+2,y+3); pdf.multi_cell(w_caso-4,h,cl)
        pdf.set_xy(x+w_id+w_caso+2,y+3); pdf.multi_cell(w_passos-4,h,pl)
        pdf.set_font("Helvetica","B",9)
        pdf.set_xy(x+w_id+w_caso+w_passos,y+(alp/2)-2); pdf.cell(w_status,4,sl,align="C")
        yo = y+alp
        if ob:
            if "Reprovado" in so: pdf.set_fill_color(255,235,235); pdf.set_text_color(116,42,42)
            else: pdf.set_fill_color(255,244,225); pdf.set_text_color(123,52,30)
            pdf.rect(x,yo,lt,ao,style="F"); pdf.rect(x,yo,lt,ao)
            pdf.set_font("Helvetica","B",8); pdf.set_xy(x+3,yo+2); pdf.write(h,ol)
            pdf.set_font("Helvetica","",8)
            pdf.set_xy(x+3+pdf.get_string_width(ol),yo+2)
            pdf.multi_cell(lt-6-pdf.get_string_width(ol),h,ob)
        pdf.set_xy(10,yo+ao)
    return bytes(pdf.output())


# ── CALLBACKS ─────────────────────────────────────────────────────────────────

def atualizar_status(id_teste):
    st.session_state.resultados[id_teste] = st.session_state[f"status_{id_teste}"]
    if st.session_state.resultados[id_teste] not in STATUS_COM_OBSERVACAO:
        st.session_state.observacoes[id_teste] = ""
    salvar_sessao()


def atualizar_observacao(id_teste):
    st.session_state.observacoes[id_teste] = st.session_state[f"obs_{id_teste}"]
    salvar_sessao()


def salvar_config():
    st.session_state.config = {
        "org": st.session_state.cfg_org, "terminal": st.session_state.cfg_terminal,
        "sn": st.session_state.cfg_sn, "so": st.session_state.cfg_so,
        "bundle": st.session_state.cfg_bundle, "qa": st.session_state.cfg_qa,
    }
    st.session_state.config_aberta = False
    qa = st.session_state.config.get("qa", "").strip()
    config_salva, resultados_salvos, observacoes_salvas = carregar_sessao(qa)
    if resultados_salvos:
        st.session_state.resultados = resultados_salvos
        st.session_state.observacoes = observacoes_salvas
    salvar_sessao()


# ── FORM CONFIG ───────────────────────────────────────────────────────────────

def renderizar_form_config():
    st.markdown("## ⚙️ Configuração da Rodada de Testes")
    st.markdown("Preencha as informações abaixo. Todos os campos são opcionais.")
    st.markdown("---")
    cfg = st.session_state.config
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("🏢 ORG", ["","STONE","TON"],
                     index=["","STONE","TON"].index(cfg.get("org","")) if cfg.get("org","") in ["","STONE","TON"] else 0,
                     key="cfg_org")
        st.text_input("🔢 SN (Serial Number)", value=cfg.get("sn",""), key="cfg_sn")
        st.text_input("📦 BUNDLE", value=cfg.get("bundle",""), key="cfg_bundle")
    with col2:
        st.selectbox("🖥️ TERMINAL", ["","P2-B","P2A11"],
                     index=["","P2-B","P2A11"].index(cfg.get("terminal","")) if cfg.get("terminal","") in ["","P2-B","P2A11"] else 0,
                     key="cfg_terminal")
        st.text_input("💻 SO (Sistema Operacional)", value=cfg.get("so",""), key="cfg_so")
        st.text_input("👤 QA Responsável", value=cfg.get("qa",""), key="cfg_qa")
    st.markdown("---")
    st.button("✅ Salvar e Continuar", on_click=salvar_config, type="primary")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    total_itens = min(len(CASOS_DE_TESTE), len(PASSOS_EXECUCAO))
    lista_ids = [f"TC-{str(i).zfill(3)}" for i in range(1, total_itens + 1)]

    if "resultados" not in st.session_state:
        st.session_state.config = CONFIG_PADRAO.copy()
        st.session_state.resultados = {id_t: "Não Executado" for id_t in lista_ids}
        st.session_state.observacoes = {id_t: "" for id_t in lista_ids}
        st.session_state.config_aberta = True
    for k, v in [("config_aberta", False), ("confirmar_reset", False),
                 ("tc_capturando", None), ("_adb_proc", None),
                 ("adb_device", None), ("adb_packages", [])]:
        if k not in st.session_state:
            st.session_state[k] = v

    df = pd.DataFrame({
        "ID": lista_ids,
        "Caso de Teste": CASOS_DE_TESTE[:total_itens],
        "Descrição / Passos": PASSOS_EXECUCAO[:total_itens]
    })

    if st.session_state.config_aberta:
        renderizar_form_config()
        return

    cfg = st.session_state.config
    valores_atuais = list(st.session_state.resultados.values())
    qtd_ap = valores_atuais.count("Aprovado ✅")
    qtd_rp = valores_atuais.count("Reprovado ❌")
    qtd_na = valores_atuais.count("Não Aplicável ⚠️")
    qtd_ne = valores_atuais.count("Não Executado")

    # ── SIDEBAR ──
    st.sidebar.markdown("## 🗂️ Dados da Rodada")
    for label, val in [("ORG",cfg.get("org","")),("Terminal",cfg.get("terminal","")),
                       ("SN",cfg.get("sn","")),("SO",cfg.get("so","")),
                       ("Bundle",cfg.get("bundle","")),("QA",cfg.get("qa",""))]:
        st.sidebar.markdown(f"**{label}:** {val if val else '—'}")
    if st.sidebar.button("✏️ Editar Configuração"):
        st.session_state.config_aberta = True
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 Sessão")
    if st.sidebar.button("💾 Salvar Progresso", use_container_width=True):
        salvar_sessao()
        st.sidebar.success("Salvo!")

    if not st.session_state.confirmar_reset:
        if st.sidebar.button("🔄 Iniciar do Zero", use_container_width=True):
            st.session_state.confirmar_reset = True
            st.rerun()
    else:
        st.sidebar.warning("⚠️ Apagará todo o progresso. Confirma?")
        cs, cn = st.sidebar.columns(2)
        with cs:
            if st.button("✅ Sim", use_container_width=True):
                limpar_sessao(lista_ids); st.rerun()
        with cn:
            if st.button("❌ Não", use_container_width=True):
                st.session_state.confirmar_reset = False; st.rerun()

    # ── ADB SIDEBAR ──
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📱 Captura de Log (ADB)")

    dispositivos = listar_dispositivos()
    if not dispositivos:
        st.sidebar.caption("Nenhum dispositivo USB encontrado.")
        adb_ativo = False
    else:
        device = st.sidebar.selectbox("Dispositivo:", dispositivos, key="adb_device_select")
        st.session_state.adb_device = device

        if st.sidebar.button("🔍 Buscar apps Stone/Ton"):
            with st.sidebar:
                with st.spinner("Buscando..."):
                    st.session_state.adb_packages = listar_packages_stone(device)

        if st.session_state.adb_packages:
            st.sidebar.caption(f"✅ {len(st.session_state.adb_packages)} packages encontrados")
            for p in st.session_state.adb_packages:
                st.sidebar.caption(f"• `{p.split('.')[-1]}`")
            adb_ativo = True
        else:
            st.sidebar.caption("Clique em 'Buscar apps' para detectar packages.")
            adb_ativo = False

    # Logs salvos na sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📁 Logs Salvos")
    arquivos_log = sorted(LOG_DIR.glob("*.txt"), reverse=True)
    if not arquivos_log:
        st.sidebar.caption("Nenhum log capturado ainda.")
    else:
        for arq in arquivos_log:
            kb = arq.stat().st_size / 1024
            st.sidebar.markdown(f"📄 `{arq.name[:30]}` — {kb:.1f}KB")
            col_dl, col_del = st.sidebar.columns(2)
            with col_dl:
                with open(arq, "rb") as f:
                    st.sidebar.download_button("⬇️", data=f.read(), file_name=arq.name,
                                               mime="text/plain", key=f"dl_{arq.name}")
            with col_del:
                if st.sidebar.button("🗑️", key=f"del_{arq.name}"):
                    arq.unlink(); st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📈 Resumo Executivo")
    for bg, borda, titulo, val in [
        ("#f0f4f8","#1a365d","Total de Casos",total_itens),
        ("#e6fffa","#319795","Aprovado ✅",qtd_ap),
        ("#fff5f5","#e53e3e","Reprovado ❌",qtd_rp),
        ("#fffaf0","#dd6b20","Não Aplicável ⚠️",qtd_na),
        ("#edf2f7","#4a5568","Não Executados",qtd_ne),
    ]:
        st.sidebar.markdown(f"""
            <div style="padding:10px;border-radius:6px;background-color:{bg};border-left:5px solid {borda};margin-bottom:10px;">
                <span style="font-size:13px;color:{borda};font-weight:bold;">{titulo}</span><br>
                <span style="font-size:20px;font-weight:bold;">{val}</span>
            </div>
        """, unsafe_allow_html=True)

    st.sidebar.markdown("### 📄 Exportar")
    try:
        pdf_bytes = gerar_pdf_fpdf(df, st.session_state.resultados, st.session_state.observacoes, cfg)
        st.sidebar.download_button("Baixar Relatório (PDF)", data=pdf_bytes,
                                   file_name="relatorio_casos_de_teste.pdf", mime="application/pdf")
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar PDF: {e}")

    # ── CONTEÚDO PRINCIPAL ──
    st.title("📋 Gerenciador de Casos de Teste")
    st.write(f"Exibindo os **{total_itens}** casos de teste cadastrados.")
    if st.session_state.tc_capturando:
        st.info(f"🔴 Capturando log de **{st.session_state.tc_capturando}** — clique ⏹️ no caso para parar.")
    st.markdown("---")

    for index, row in df.iterrows():
        id_teste = row["ID"]
        num_teste = index + 1
        status_atual = st.session_state.resultados.get(id_teste, "Não Executado")
        obs_atual = st.session_state.observacoes.get(id_teste, "")

        if num_teste in MAPEAMENTO_SECOES:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='background-color:#1a365d;padding:12px 15px;border-radius:4px;"
                f"margin-bottom:20px;color:#ffffff;font-size:18px;font-weight:bold;'>"
                f"{MAPEAMENTO_SECOES[num_teste]}</div>", unsafe_allow_html=True)

        if status_atual == "Aprovado ✅":
            cf, cb, ct = "#e6fffa","#319795","#234e52"
        elif status_atual == "Reprovado ❌":
            cf, cb, ct = "#fff5f5","#e53e3e","#742a2a"
        elif status_atual == "Não Aplicável ⚠️":
            cf, cb, ct = "#fffaf0","#dd6b20","#7b341e"
        else:
            cf, cb, ct = "#f7fafc","#cbd5e0","#4a5568"

        with st.container():
            st.markdown(
                f"<div style='padding:12px;border-radius:6px;background-color:{cf};"
                f"border-left:6px solid {cb};color:{ct};margin-bottom:10px;'>"
                f"<h4 style='margin:0;color:{ct};'>🆔 {id_teste} — {row['Caso de Teste']}</h4>"
                f"<span style='font-size:13px;'><b>Status Atual:</b> {status_atual}</span>"
                f"</div>", unsafe_allow_html=True)

            st.write(f"**Passos para Execução:**\n{row['Descrição / Passos']}")

            # Linha de controles: selectbox + botão ADB
            col_sel, col_adb = st.columns([4, 1])
            with col_sel:
                st.selectbox(f"Alterar status de {id_teste}:", OPCOES_STATUS,
                             index=OPCOES_STATUS.index(status_atual) if status_atual in OPCOES_STATUS else 0,
                             key=f"status_{id_teste}", on_change=atualizar_status, args=(id_teste,))

            with col_adb:
                if adb_ativo:
                    tc_cap = st.session_state.tc_capturando
                    if tc_cap == id_teste:
                        # Este TC está sendo capturado
                        arq = Path(st.session_state.get("log_arquivo_atual",""))
                        kb = arq.stat().st_size/1024 if arq.exists() else 0
                        st.markdown(f"<br>", unsafe_allow_html=True)
                        if st.button(f"⏹️ Parar\n{kb:.1f}KB", key=f"adb_{id_teste}", use_container_width=True):
                            parar_captura(); st.rerun()
                    elif tc_cap is None:
                        # Nenhum TC capturando — mostra botão iniciar
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("▶️ Log", key=f"adb_{id_teste}", use_container_width=True):
                            iniciar_captura_tc(id_teste, st.session_state.adb_device,
                                               st.session_state.adb_packages)
                            st.rerun()
                    else:
                        # Outro TC capturando — botão desabilitado
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.button("▶️ Log", key=f"adb_{id_teste}", disabled=True, use_container_width=True)

            if status_atual in STATUS_COM_OBSERVACAO:
                label_obs = "📝 Descrição do defeito / motivo:" if status_atual == "Reprovado ❌" else "📝 Motivo de não aplicabilidade:"
                st.text_area(label_obs, value=obs_atual, key=f"obs_{id_teste}", height=80,
                             placeholder="Descreva o defeito encontrado ou o motivo...",
                             on_change=atualizar_observacao, args=(id_teste,))

            st.markdown("---")


if __name__ == "__main__":
    main()