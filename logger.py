import streamlit as st
import subprocess
import threading
import datetime
from pathlib import Path

st.set_page_config(page_title="ADB Log Capturador", layout="wide")

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

try:
    from dados import CASOS_DE_TESTE, PASSOS_EXECUCAO
    total_itens = min(len(CASOS_DE_TESTE), len(PASSOS_EXECUCAO))
    LISTA_TCS = [f"TC-{str(i).zfill(3)}" for i in range(1, total_itens + 1)]
except Exception:
    LISTA_TCS = [f"TC-{str(i).zfill(3)}" for i in range(1, 165)]


def rodar_adb(args, timeout=15):
    try:
        result = subprocess.run(
            ["adb"] + args,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return "", "ADB não encontrado."
    except subprocess.TimeoutExpired:
        return "", "Timeout."


def listar_dispositivos():
    stdout, _ = rodar_adb(["devices"])
    dispositivos = []
    for linha in stdout.splitlines()[1:]:
        if "\tdevice" in linha:
            dispositivos.append(linha.split("\t")[0].strip())
    return dispositivos


def listar_packages_stone(device_id):
    stdout, _ = rodar_adb(["-s", device_id, "shell", "pm", "list", "packages"])
    packages = []
    for linha in stdout.splitlines():
        pkg = linha.replace("package:", "").strip()
        if "stone" in pkg.lower() or "ton" in pkg.lower():
            packages.append(pkg)
    return sorted(packages)


def get_pid(device_id, package):
    stdout, _ = rodar_adb(["-s", device_id, "shell", "ps", "-A"])
    for linha in stdout.splitlines():
        if package in linha:
            partes = linha.split()
            if len(partes) >= 2:
                try:
                    return partes[1]
                except Exception:
                    pass
    return None


def capturar_log(device_id, package, tc, nome_arquivo, pid):
    """Roda em thread separada — grava diretamente no arquivo sem depender do Streamlit."""
    # NÃO limpa logcat — preserva logs já existentes do app
    cmd = ["adb", "-s", device_id, "logcat", "-v", "threadtime"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        st.session_state._processo = proc

        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write("=== LOG CAPTURADO ===\n")
            f.write(f"TC: {tc}\n")
            f.write(f"Package: {package}\n")
            f.write(f"Device: {device_id}\n")
            f.write(f"Inicio: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"PID: {pid if pid else 'nao encontrado'}\n")
            f.write("=" * 50 + "\n\n")

            for linha in proc.stdout:
                # Verifica flag de parada via arquivo sentinela
                if Path("logs/.parar").exists():
                    break

                incluir = False
                if pid:
                    partes = linha.split()
                    # formato: DATA HORA PID TID LEVEL TAG: msg
                    if len(partes) >= 3 and partes[2] == pid:
                        incluir = True
                    # também inclui linhas que mencionam o package explicitamente
                    if package in linha:
                        incluir = True
                else:
                    # sem PID: grava tudo
                    incluir = True

                if incluir:
                    f.write(linha)
                    f.flush()

    except Exception as e:
        with open(nome_arquivo, "a", encoding="utf-8") as f:
            f.write(f"\n[ERRO NA CAPTURA: {e}]\n")


def iniciar_captura(device_id, package, tc):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = LOG_DIR / f"{tc}_{package}_{timestamp}.txt"

    # Remove sentinela de parada se existir
    sentinela = Path("logs/.parar")
    if sentinela.exists():
        sentinela.unlink()

    pid = get_pid(device_id, package)

    st.session_state.capturando = True
    st.session_state.arquivo_atual = str(nome_arquivo)
    st.session_state.pid_atual = pid

    thread = threading.Thread(
        target=capturar_log,
        args=(device_id, package, tc, nome_arquivo, pid),
        daemon=True
    )
    thread.start()
    st.session_state._thread = thread


def parar_captura():
    # Sinaliza parada via arquivo sentinela (thread-safe, sem depender de session_state)
    Path("logs/.parar").touch()
    st.session_state.capturando = False
    proc = st.session_state.get("_processo")
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass
    st.session_state._processo = None


def main():
    st.title("📱 ADB Log Capturador")
    st.markdown("Capture logs do dispositivo Android vinculados a casos de teste.")
    st.markdown("---")

    for key, val in [("capturando", False), ("arquivo_atual", ""),
                     ("pid_atual", None), ("_processo", None), ("packages", [])]:
        if key not in st.session_state:
            st.session_state[key] = val

    # --- DISPOSITIVO ---
    st.subheader("🔌 Dispositivo")
    col1, col2 = st.columns([3, 1])
    dispositivos = listar_dispositivos()

    with col2:
        if st.button("🔄 Atualizar"):
            st.rerun()

    if not dispositivos:
        st.warning("Nenhum dispositivo encontrado. Conecte via USB e habilite depuração USB.")
        st.code("adb devices", language="bash")
        st.stop()

    with col1:
        device_selecionado = st.selectbox("Dispositivo conectado:", dispositivos)

    st.success(f"✅ Dispositivo: `{device_selecionado}`")
    st.markdown("---")

    # --- PACKAGES ---
    st.subheader("📦 Aplicativo para monitorar")

    if st.button("🔍 Buscar apps Stone/Ton no dispositivo"):
        with st.spinner("Buscando packages..."):
            pkgs = listar_packages_stone(device_selecionado)
            st.session_state.packages = pkgs

    if not st.session_state.packages:
        st.info("Clique em 'Buscar apps Stone/Ton' para listar os aplicativos.")
        st.stop()

    package_selecionado = st.selectbox("Package a monitorar:", st.session_state.packages)

    pid_atual = get_pid(device_selecionado, package_selecionado)
    if pid_atual:
        st.caption(f"✅ Processo ativo — PID: `{pid_atual}`")
    else:
        st.caption("⚠️ Processo não encontrado — abra o app no POS antes de capturar.")

    st.markdown("---")

    # --- TC ---
    st.subheader("🆔 Caso de Teste vinculado")
    tc_selecionado = st.selectbox("Selecione o TC:", LISTA_TCS)
    st.markdown("---")

    # --- CAPTURA ---
    st.subheader("⏺️ Captura de Log")

    if not st.session_state.capturando:
        col_ini, _ = st.columns(2)
        with col_ini:
            if st.button("▶️ Iniciar Captura", type="primary", use_container_width=True):
                iniciar_captura(device_selecionado, package_selecionado, tc_selecionado)
                st.rerun()
    else:
        st.success(f"🔴 Capturando logs do PID `{st.session_state.pid_atual}`")
        st.info(f"Arquivo: `{st.session_state.arquivo_atual}`\n\nUse o app no POS agora. Clique **Parar** quando terminar.")

        # Mostra tamanho atual do arquivo
        arq = Path(st.session_state.arquivo_atual)
        if arq.exists():
            kb = arq.stat().st_size / 1024
            st.caption(f"Tamanho atual: {kb:.1f} KB")

        if st.button("⏹️ Parar Captura", type="secondary"):
            parar_captura()
            st.rerun()

    st.markdown("---")

    # --- LOGS SALVOS ---
    st.subheader("📁 Logs Salvos")
    arquivos = sorted(LOG_DIR.glob("*.txt"), reverse=True)

    if not arquivos:
        st.info("Nenhum log capturado ainda.")
    else:
        for arq in arquivos:
            kb = arq.stat().st_size / 1024
            col_nome, col_dl, col_del = st.columns([4, 1, 1])
            with col_nome:
                st.markdown(f"📄 `{arq.name}` — {kb:.1f} KB")
            with col_dl:
                with open(arq, "rb") as f:
                    st.download_button(
                        label="⬇️ Baixar",
                        data=f.read(),
                        file_name=arq.name,
                        mime="text/plain",
                        key=f"dl_{arq.name}"
                    )
            with col_del:
                if st.button("🗑️ Excluir", key=f"del_{arq.name}"):
                    arq.unlink()
                    st.rerun()


if __name__ == "__main__":
    main()