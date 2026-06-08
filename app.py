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
    st.error(f"Erro ao carregar dados.py: {e}")
    st.stop()

MAPEAMENTO_SECOES = {
    1:"🚀 SEÇÃO LAUNCHER",10:"💳 SEÇÃO PAGAMENTO",61:"❌ SEÇÃO CANCELAMENTO",
    72:"🔌 SEÇÃO CONEXÃO",87:"🔓 SEÇÃO ATIVAÇÃO",98:"⚙️ SEÇÃO AJUSTES",
    114:"❓ SEÇÃO AJUDA",122:"🧮 SEÇÃO CALCULADORA",125:"📊 SEÇÃO SIMULADOR DE VENDAS",
    133:"🧾 SEÇÃO REIMPRESSÃO / RECIBOS",142:"📈 SEÇÃO RELATÓRIO",
    151:"🔒 SEÇÃO FECHAMENTO",157:"🏪 SEÇÃO LOJA",162:"✨ SEÇÃO NOVIDADES"
}
OPCOES_STATUS = ["Não Executado","Aprovado ✅","Reprovado ❌","Não Aplicável ⚠️"]
STATUS_COM_OBSERVACAO = {"Reprovado ❌","Não Aplicável ⚠️"}
CONFIG_PADRAO = {"org":"","terminal":"","sn":"","so":"","bundle":"","qa":""}
SAVES_DIR = Path("saves")
LOG_DIR = Path("logs")
SAVES_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


# ══ PERSISTÊNCIA ══════════════════════════════════════════════════════════════

def _arquivo_save():
    qa = st.session_state.get("config",{}).get("qa","").strip()
    nome = "".join(c for c in (qa or "anonimo") if c.isalnum() or c in "-_").lower()
    return SAVES_DIR / f"sessao_{nome or 'anonimo'}.json"

def salvar_sessao():
    _arquivo_save().write_text(
        json.dumps({"config":st.session_state.config,
                    "resultados":st.session_state.resultados,
                    "observacoes":st.session_state.observacoes},
                   ensure_ascii=False, indent=2), encoding="utf-8")

def carregar_sessao(qa_nome=""):
    if not qa_nome:
        return None,None,None
    nome = "".join(c for c in qa_nome.strip() if c.isalnum() or c in "-_").lower()
    arq = SAVES_DIR / f"sessao_{nome}.json"
    if arq.exists():
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
            return d.get("config"),d.get("resultados"),d.get("observacoes")
        except Exception:
            pass
    return None,None,None

def limpar_sessao(lista_ids):
    arq = _arquivo_save()
    if arq.exists(): arq.unlink()
    st.session_state.config = CONFIG_PADRAO.copy()
    st.session_state.resultados = {i:"Não Executado" for i in lista_ids}
    st.session_state.observacoes = {i:"" for i in lista_ids}
    st.session_state.config_aberta = True
    st.session_state.confirmar_reset = False


# ══ ADB ═══════════════════════════════════════════════════════════════════════

_ADB_CANDIDATES = [
    "adb",
    r"C:\Variaveis_de_ambiente\scrcpy-win64-v2.7\adb.exe",
    r"C:\Users\Inovare\AppData\Local\Android\Sdk\platform-tools\adb.exe",
]

def _adb_bin():
    import shutil
    for p in _ADB_CANDIDATES:
        found = shutil.which(p)
        if found:
            return found
        if p != "adb" and Path(p).exists():
            return p
    return "adb"

def rodar_adb(args, timeout=10):
    try:
        r = subprocess.run([_adb_bin()]+args, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return "","ADB não encontrado"
    except subprocess.TimeoutExpired:
        return "","Timeout"

def listar_dispositivos():
    stdout,_ = rodar_adb(["devices"])
    return [l.split("\t")[0].strip() for l in stdout.splitlines()[1:] if "\tdevice" in l]

def listar_packages_stone(device_id):
    stdout,_ = rodar_adb(["-s",device_id,"shell","pm","list","packages"])
    return sorted(l.replace("package:","").strip() for l in stdout.splitlines()
                  if "stone" in l.lower() or "ton" in l.lower())

def get_pids_stone(device_id, packages):
    stdout,_ = rodar_adb(["-s",device_id,"shell","ps","-A"])
    pids = {}
    for linha in stdout.splitlines():
        for pkg in packages:
            if pkg in linha and pkg not in pids:
                p = linha.split()
                if len(p) >= 2:
                    try: pids[pkg] = p[1]
                    except: pass
    return pids

def _capturar_thread(device_id, packages, tc, nome_arquivo):
    sentinela = LOG_DIR/".parar"
    if sentinela.exists(): sentinela.unlink()
    # Pega PIDs na hora de iniciar (melhor esforco)
    pids = get_pids_stone(device_id, packages)
    pid_set = set(pids.values())
    try:
        proc = subprocess.Popen(
            [_adb_bin(),"-s",device_id,"logcat","-v","threadtime"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace")
        st.session_state._adb_proc = proc
        with open(nome_arquivo,"w",encoding="utf-8") as f:
            f.write("=== LOG CAPTURADO ===\n")
            f.write(f"TC: {tc}\nDevice: {device_id}\n")
            if pids:
                for pkg,pid in pids.items(): f.write(f"  {pkg} (PID {pid})\n")
            else:
                f.write("  PIDs nao encontrados - filtrando por package name\n")
            f.write(f"Inicio: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("="*50+"\n\n")
            for linha in proc.stdout:
                if sentinela.exists(): break
                partes = linha.split()
                pid_match = pid_set and len(partes)>=3 and partes[2] in pid_set
                pkg_match = any(pkg in linha for pkg in packages)
                if pid_match or pkg_match:
                    f.write(linha); f.flush()
    except Exception as e:
        with open(nome_arquivo,"a",encoding="utf-8") as f:
            f.write(f"\n[ERRO: {e}]\n")

def iniciar_captura_tc(tc, device_id, packages):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = LOG_DIR/f"{tc}_stone_{timestamp}.txt"
    st.session_state.tc_capturando = tc
    st.session_state.log_arquivo_atual = str(nome_arquivo)
    threading.Thread(target=_capturar_thread,
                     args=(device_id,packages,tc,nome_arquivo),
                     daemon=True).start()
    return True

def parar_captura():
    (LOG_DIR/".parar").touch()
    st.session_state.tc_capturando = None
    proc = st.session_state.get("_adb_proc")
    if proc:
        try: proc.terminate()
        except: pass
    st.session_state._adb_proc = None


# ══ PDF ═══════════════════════════════════════════════════════════════════════

class RelatorioPDF(FPDF):
    def header(self):
        self.set_font("Helvetica","B",18); self.set_text_color(26,54,93)
        self.cell(0,10,"Relatorio de Execucao de Testes",ln=True); self.ln(4)
    def footer(self):
        self.set_y(-15); self.set_font("Helvetica","I",8)
        self.set_text_color(160,174,192)
        self.cell(0,10,f"Pagina {self.page_no()}/{{nb}}",align="R")

def tratar_texto_pdf(texto):
    if not texto: return ""
    texto = (str(texto).replace("✅","[Aprovado]").replace("❌","[Reprovado]")
             .replace("⚠️","[Nao Aplicavel]").replace("⚡",""))
    for o,s in {"á":"a","à":"a","ã":"a","â":"a","Á":"A","À":"A","Ã":"A","Â":"A",
                "é":"e","è":"e","ê":"e","É":"E","È":"E","Ê":"E",
                "í":"i","ì":"i","î":"i","Í":"I","Ì":"I","Î":"I",
                "ó":"o","ò":"o","ô":"o","õ":"o","Ó":"O","Ò":"O","Ô":"O","Õ":"O",
                "ú":"u","ù":"u","û":"u","Ú":"U","Ù":"U","Û":"U",
                "ç":"c","Ç":"C","º":".","ª":".","–":"-","—":"-",
                "\u2018":"'","\u2019":"'","\u201c":'"',"\u201d":'"'}.items():
        texto = texto.replace(o,s)
    return texto.encode("latin-1","ignore").decode("latin-1")

def gerar_pdf_fpdf(df_base, resultados, observacoes, config):
    df = df_base.copy()
    df["Resultado"] = df["ID"].map(lambda x: resultados.get(x,"Não Executado"))
    df["Observacao"] = df["ID"].map(lambda x: observacoes.get(x,""))
    qtd_total=len(df)
    qtd_ap=len(df[df["Resultado"]=="Aprovado ✅"])
    qtd_rp=len(df[df["Resultado"]=="Reprovado ❌"])
    qtd_na=len(df[df["Resultado"]=="Não Aplicável ⚠️"])
    qtd_ne=qtd_total-(qtd_ap+qtd_rp+qtd_na)
    pdf=RelatorioPDF(); pdf.alias_nb_pages(); pdf.add_page()
    pdf.set_font("Helvetica","B",11); pdf.set_text_color(45,55,72)
    pdf.cell(0,8,"Identificacao da Rodada:",ln=True); pdf.ln(2)
    campos=[("ORG",config.get("org","")),("Terminal",config.get("terminal","")),
            ("SN",config.get("sn","")),("SO",config.get("so","")),
            ("Bundle",config.get("bundle","")),("QA Responsavel",config.get("qa",""))]
    wl,wv,gap=32,62,4
    for (la,va),(lb,vb) in [(campos[i],campos[i+3]) for i in range(3)]:
        pdf.set_fill_color(43,108,176); pdf.set_text_color(255,255,255)
        pdf.set_font("Helvetica","B",8); pdf.cell(wl,8,f" {la}",border=1,fill=True)
        pdf.set_fill_color(248,250,252); pdf.set_text_color(45,55,72)
        pdf.set_font("Helvetica","",9); pdf.cell(wv,8,f" {tratar_texto_pdf(va)}",border=1,fill=True)
        pdf.cell(gap,8,"",border=0)
        pdf.set_fill_color(43,108,176); pdf.set_text_color(255,255,255)
        pdf.set_font("Helvetica","B",8); pdf.cell(wl,8,f" {lb}",border=1,fill=True)
        pdf.set_fill_color(248,250,252); pdf.set_text_color(45,55,72)
        pdf.set_font("Helvetica","",9); pdf.cell(wv,8,f" {tratar_texto_pdf(vb)}",border=1,fill=True,ln=True)
    pdf.ln(6)
    pdf.set_font("Helvetica","B",11); pdf.set_text_color(45,55,72)
    pdf.cell(0,8,"Resumo Executivo da Rodada:",ln=True); pdf.ln(2)
    pdf.set_font("Helvetica","",9); pdf.set_text_color(45,55,72)
    for cor,txt in [((240,244,248),f" Total: {qtd_total}"),((230,255,250),f" Aprovado: {qtd_ap}"),
                    ((255,245,245),f" Reprovado: {qtd_rp}"),((255,250,240),f" Nao Aplic.: {qtd_na}"),
                    ((247,250,252),f" Nao Exec.: {qtd_ne}")]:
        pdf.set_fill_color(*cor); pdf.cell(38,10,txt,border=1,fill=True)
    pdf.ln(True); pdf.ln(8)
    wid,wc,wp,ws=18,54,93,25; lt=wid+wc+wp+ws
    pdf.set_font("Helvetica","B",10); pdf.set_fill_color(43,108,176); pdf.set_text_color(255,255,255)
    pdf.cell(wid,10,"ID",border=1,fill=True,align="C")
    pdf.cell(wc,10," Caso de Teste",border=1,fill=True)
    pdf.cell(wp,10," Passos de Execucao",border=1,fill=True)
    pdf.cell(ws,10,"Resultado",border=1,fill=True,ln=True,align="C")
    h=4.5
    for _,row in df.iterrows():
        so=str(row["Resultado"]); sl=so.replace(" ✅","").replace(" ❌","").replace(" ⚠️","")
        cl=tratar_texto_pdf(row["Caso de Teste"]); pl=tratar_texto_pdf(row["Descrição / Passos"])
        ob=tratar_texto_pdf(str(row["Observacao"]).strip()) if row["Observacao"] else ""
        lc=len(pdf.multi_cell(wc-4,h,cl,split_only=True))
        lp=len(pdf.multi_cell(wp-4,h,pl,split_only=True))
        alp=(max(lc,lp,1)*h)+6
        ol="Observacao: "
        ao=((len(pdf.multi_cell(lt-6,h,ol+ob,split_only=True))*h)+4) if ob else 0
        if pdf.get_y()+alp+ao>275: pdf.add_page()
        x,y=pdf.get_x(),pdf.get_y()
        pdf.rect(x,y,wid,alp); pdf.rect(x+wid,y,wc,alp); pdf.rect(x+wid+wc,y,wp,alp)
        if "Aprovado" in so: pdf.set_fill_color(230,255,250); pdf.set_text_color(35,78,82)
        elif "Reprovado" in so: pdf.set_fill_color(255,245,245); pdf.set_text_color(116,42,42)
        elif "Não Aplicável" in so: pdf.set_fill_color(255,250,240); pdf.set_text_color(123,52,30)
        else: pdf.set_fill_color(247,250,252); pdf.set_text_color(74,85,104)
        pdf.rect(x+wid+wc+wp,y,ws,alp,style="F"); pdf.rect(x+wid+wc+wp,y,ws,alp)
        pdf.set_font("Helvetica","B",9); pdf.set_text_color(43,108,176)
        pdf.set_xy(x,y+(alp/2)-2); pdf.cell(wid,4,str(row["ID"]),align="C")
        pdf.set_font("Helvetica","",8.5); pdf.set_text_color(45,55,72)
        pdf.set_xy(x+wid+2,y+3); pdf.multi_cell(wc-4,h,cl)
        pdf.set_xy(x+wid+wc+2,y+3); pdf.multi_cell(wp-4,h,pl)
        pdf.set_font("Helvetica","B",9)
        pdf.set_xy(x+wid+wc+wp,y+(alp/2)-2); pdf.cell(ws,4,sl,align="C")
        yo=y+alp
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


# ══ CALLBACKS ═════════════════════════════════════════════════════════════════

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
        "org":st.session_state.cfg_org,"terminal":st.session_state.cfg_terminal,
        "sn":st.session_state.cfg_sn,"so":st.session_state.cfg_so,
        "bundle":st.session_state.cfg_bundle,"qa":st.session_state.cfg_qa}
    st.session_state.config_aberta = False
    qa = st.session_state.config.get("qa","").strip()
    cfg_s,res_s,obs_s = carregar_sessao(qa)
    if res_s:
        st.session_state.resultados = res_s
        st.session_state.observacoes = obs_s
    salvar_sessao()


# ══ FORM CONFIG ═══════════════════════════════════════════════════════════════

def renderizar_form_config():
    st.markdown("## ⚙️ Configuração da Rodada de Testes")
    st.markdown("Preencha as informações abaixo. Todos os campos são opcionais.")
    st.markdown("---")
    cfg = st.session_state.config
    c1,c2 = st.columns(2)
    with c1:
        st.selectbox("🏢 ORG",["","STONE","TON"],
                     index=["","STONE","TON"].index(cfg.get("org","")) if cfg.get("org","") in ["","STONE","TON"] else 0,
                     key="cfg_org")
        st.text_input("🔢 SN (Serial Number)",value=cfg.get("sn",""),key="cfg_sn")
        st.text_input("📦 BUNDLE",value=cfg.get("bundle",""),key="cfg_bundle")
    with c2:
        st.selectbox("🖥️ TERMINAL",["","P2-B","P2A11"],
                     index=["","P2-B","P2A11"].index(cfg.get("terminal","")) if cfg.get("terminal","") in ["","P2-B","P2A11"] else 0,
                     key="cfg_terminal")
        st.text_input("💻 SO (Sistema Operacional)",value=cfg.get("so",""),key="cfg_so")
        st.text_input("👤 QA Responsável",value=cfg.get("qa",""),key="cfg_qa")
    st.markdown("---")
    st.button("✅ Salvar e Continuar",on_click=salvar_config,type="primary")


# ══ MAIN ══════════════════════════════════════════════════════════════════════

def main():
    total_itens = min(len(CASOS_DE_TESTE),len(PASSOS_EXECUCAO))
    lista_ids = [f"TC-{str(i).zfill(3)}" for i in range(1,total_itens+1)]

    # Inicializa session_state
    if "resultados" not in st.session_state:
        st.session_state.config = CONFIG_PADRAO.copy()
        st.session_state.resultados = {i:"Não Executado" for i in lista_ids}
        st.session_state.observacoes = {i:"" for i in lista_ids}
        st.session_state.config_aberta = True
        st.session_state.confirmar_reset = False
        st.session_state.tc_capturando = None
        st.session_state._adb_proc = None
        st.session_state.adb_packages = []
        st.session_state.adb_device = None
        st.session_state.log_arquivo_atual = ""

    # Garante chaves ADB em sessões já existentes
    for k,v in [("config_aberta",False),("confirmar_reset",False),
                ("tc_capturando",None),("_adb_proc",None),
                ("adb_packages",[]),("adb_device",None),("log_arquivo_atual","")]:
        if k not in st.session_state:
            st.session_state[k] = v

    df = pd.DataFrame({
        "ID":lista_ids,
        "Caso de Teste":CASOS_DE_TESTE[:total_itens],
        "Descrição / Passos":PASSOS_EXECUCAO[:total_itens]
    })

    if st.session_state.config_aberta:
        renderizar_form_config()
        return

    cfg = st.session_state.config
    vals = list(st.session_state.resultados.values())
    qtd_aprovado = vals.count("Aprovado ✅")
    qtd_reprovado = vals.count("Reprovado ❌")
    qtd_nao_aplic = vals.count("Não Aplicável ⚠️")
    qtd_nao_exec = vals.count("Não Executado")

    # ── SIDEBAR: DADOS DA RODADA ──
    st.sidebar.markdown("## 🗂️ Dados da Rodada")
    for lbl,val in [("ORG",cfg.get("org","")),("Terminal",cfg.get("terminal","")),
                    ("SN",cfg.get("sn","")),("SO",cfg.get("so","")),
                    ("Bundle",cfg.get("bundle","")),("QA",cfg.get("qa",""))]:
        st.sidebar.markdown(f"**{lbl}:** {val if val else '—'}")
    if st.sidebar.button("✏️ Editar Configuração"):
        st.session_state.config_aberta = True; st.rerun()

    # ── SIDEBAR: SESSÃO ──
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 Sessão")
    if st.sidebar.button("💾 Salvar Progresso",use_container_width=True):
        salvar_sessao(); st.sidebar.success("Salvo!")
    if not st.session_state.confirmar_reset:
        if st.sidebar.button("🔄 Iniciar do Zero",use_container_width=True):
            st.session_state.confirmar_reset = True; st.rerun()
    else:
        st.sidebar.warning("⚠️ Apagará todo o progresso. Confirma?")
        cs,cn = st.sidebar.columns(2)
        with cs:
            if st.button("✅ Sim",use_container_width=True):
                limpar_sessao(lista_ids); st.rerun()
        with cn:
            if st.button("❌ Não",use_container_width=True):
                st.session_state.confirmar_reset = False; st.rerun()

    # ── SIDEBAR: ADB ──
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📱 Captura de Log (ADB)")
    if st.sidebar.button("🔄 Detectar Dispositivo",use_container_width=True):
        st.rerun()
    dispositivos = listar_dispositivos()
    if not dispositivos:
        st.sidebar.warning("Nenhum dispositivo USB encontrado.")
        st.sidebar.caption("Verifique o cabo, ative depuração USB e reinicie o Streamlit.")
        adb_ativo = False
    else:
        dev = st.sidebar.selectbox("Dispositivo:",dispositivos,key="adb_device_sel")
        st.session_state.adb_device = dev
        if st.sidebar.button("🔍 Buscar apps Stone/Ton",use_container_width=True):
            with st.spinner("Buscando..."):
                st.session_state.adb_packages = listar_packages_stone(dev)
        if st.session_state.adb_packages:
            st.sidebar.success(f"✅ {len(st.session_state.adb_packages)} packages prontos")
            adb_ativo = True
        else:
            st.sidebar.caption("Clique em 'Buscar apps Stone/Ton'.")
            adb_ativo = False

    if st.session_state.tc_capturando:
        arq = Path(st.session_state.log_arquivo_atual)
        kb = arq.stat().st_size/1024 if arq.exists() else 0
        st.sidebar.info(f"🔴 Capturando **{st.session_state.tc_capturando}** — {kb:.1f} KB")
        if st.sidebar.button("⏹️ Parar Captura",use_container_width=True):
            parar_captura(); st.rerun()

    # ── SIDEBAR: LOGS SALVOS ──
    st.sidebar.markdown("### 📁 Logs Salvos")
    logs = sorted(LOG_DIR.glob("*.txt"),reverse=True)
    if not logs:
        st.sidebar.caption("Nenhum log capturado ainda.")
    else:
        for arq in logs:
            kb = arq.stat().st_size/1024
            st.sidebar.markdown(f"📄 `{arq.name[:28]}` — {kb:.1f} KB")
            c1,c2 = st.sidebar.columns(2)
            with c1:
                with open(arq,"rb") as f:
                    st.sidebar.download_button("⬇️ Baixar",data=f.read(),
                        file_name=arq.name,mime="text/plain",key=f"dl_{arq.name}")
            with c2:
                if st.sidebar.button("🗑️ Excluir",key=f"del_{arq.name}"):
                    arq.unlink(); st.rerun()

    # ── SIDEBAR: RESUMO EXECUTIVO ──
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📈 Resumo Executivo")
    for bg,bd,tit,val,ct in [
        ("#f0f4f8","#1a365d","Total de Casos",total_itens,"#0f172a"),
        ("#e6fffa","#319795","Aprovado ✅",qtd_aprovado,"#042f2e"),
        ("#fff5f5","#e53e3e","Reprovado ❌",qtd_reprovado,"#451a1a"),
        ("#fffaf0","#dd6b20","Não Aplicável ⚠️",qtd_nao_aplic,"#431407"),
        ("#edf2f7","#4a5568","Não Executados",qtd_nao_exec,"#1e293b"),
    ]:
        st.sidebar.markdown(f"""
            <div style="padding:10px;border-radius:6px;background-color:{bg};border-left:5px solid {bd};margin-bottom:10px;">
                <span style="font-size:13px;color:{bd};font-weight:bold;">{tit}</span><br>
                <span style="font-size:20px;font-weight:bold;color:{ct};">{val}</span>
            </div>""", unsafe_allow_html=True)

    # ── SIDEBAR: EXPORTAR ──
    st.sidebar.markdown("### 📄 Exportar")
    try:
        pdf_bytes = gerar_pdf_fpdf(df,st.session_state.resultados,st.session_state.observacoes,cfg)
        st.sidebar.download_button("Baixar Relatório (PDF)",data=pdf_bytes,
            file_name="relatorio_casos_de_teste.pdf",mime="application/pdf")
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar PDF: {e}")

    # ── CONTEÚDO PRINCIPAL ──
    st.title("📋 Gerenciador de Casos de Teste")
    st.write(f"Exibindo os **{total_itens}** casos de teste cadastrados.")
    if st.session_state.tc_capturando:
        st.info(f"🔴 Capturando log de **{st.session_state.tc_capturando}** — clique ⏹️ para parar.")
    st.markdown("---")

    for index,row in df.iterrows():
        id_teste = row["ID"]
        num_teste = index+1
        status_atual = st.session_state.resultados.get(id_teste,"Não Executado")
        obs_atual = st.session_state.observacoes.get(id_teste,"")

        if num_teste in MAPEAMENTO_SECOES:
            st.markdown("<br>",unsafe_allow_html=True)
            st.markdown(
                f"<div style='background-color:#1a365d;padding:12px 15px;border-radius:4px;"
                f"margin-bottom:20px;color:#ffffff;font-size:18px;font-weight:bold;'>"
                f"{MAPEAMENTO_SECOES[num_teste]}</div>",unsafe_allow_html=True)

        if status_atual=="Aprovado ✅": cf,cb,ct="#e6fffa","#319795","#234e52"
        elif status_atual=="Reprovado ❌": cf,cb,ct="#fff5f5","#e53e3e","#742a2a"
        elif status_atual=="Não Aplicável ⚠️": cf,cb,ct="#fffaf0","#dd6b20","#7b341e"
        else: cf,cb,ct="#f7fafc","#cbd5e0","#4a5568"

        with st.container():
            st.markdown(
                f"<div style='padding:12px;border-radius:6px;background-color:{cf};"
                f"border-left:6px solid {cb};color:{ct};margin-bottom:10px;'>"
                f"<h4 style='margin:0;color:{ct};'>🆔 {id_teste} — {row['Caso de Teste']}</h4>"
                f"<span style='font-size:13px;'><b>Status Atual:</b> {status_atual}</span>"
                f"</div>",unsafe_allow_html=True)

            st.write(f"**Passos para Execução:**\n{row['Descrição / Passos']}")

            col_sel,col_adb = st.columns([4,1])
            with col_sel:
                st.selectbox(f"Alterar status de {id_teste}:",OPCOES_STATUS,
                    index=OPCOES_STATUS.index(status_atual) if status_atual in OPCOES_STATUS else 0,
                    key=f"status_{id_teste}",on_change=atualizar_status,args=(id_teste,))
            with col_adb:
                if adb_ativo:
                    tc_cap = st.session_state.tc_capturando
                    if tc_cap==id_teste:
                        arq=Path(st.session_state.log_arquivo_atual)
                        kb=arq.stat().st_size/1024 if arq.exists() else 0
                        st.markdown("<br>",unsafe_allow_html=True)
                        if st.button(f"⏹️ {kb:.0f}KB",key=f"adb_{id_teste}",use_container_width=True):
                            parar_captura(); st.rerun()
                    elif tc_cap is None:
                        st.markdown("<br>",unsafe_allow_html=True)
                        if st.button("▶️ Log",key=f"adb_{id_teste}",use_container_width=True):
                            ok=iniciar_captura_tc(id_teste,st.session_state.adb_device,
                                                  st.session_state.adb_packages)
                            if not ok: st.warning("Nenhum processo stone ativo.")
                            st.rerun()
                    else:
                        st.markdown("<br>",unsafe_allow_html=True)
                        st.button("▶️ Log",key=f"adb_{id_teste}",disabled=True,use_container_width=True)

            if status_atual in STATUS_COM_OBSERVACAO:
                lbl_obs="📝 Descrição do defeito:" if status_atual=="Reprovado ❌" else "📝 Motivo de não aplicabilidade:"
                st.text_area(lbl_obs,value=obs_atual,key=f"obs_{id_teste}",height=80,
                    placeholder="Descreva o defeito ou motivo...",
                    on_change=atualizar_observacao,args=(id_teste,))

            st.markdown("---")


if __name__ == "__main__":
    main()