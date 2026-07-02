# 📋 Gerenciador de Casos de Teste — Stone/Ton

Ferramenta para execução de casos de teste, geração de relatório em PDF e captura de log via ADB de terminais POS conectados por USB.

## Instalação (só precisa fazer uma vez)

1. Aperte a tecla **Windows**, digite `PowerShell` e abra o **Windows PowerShell** (não precisa ser administrador).
2. Cole o comando abaixo e aperte **Enter**:

   ```powershell
   Invoke-WebRequest -Uri "https://raw.githubusercontent.com/JoelRoberto/gerenciador-testes/main/instalar_e_rodar.bat" -OutFile "$env:USERPROFILE\Desktop\instalar_e_rodar.bat"
   ```

3. Isso cria o arquivo `instalar_e_rodar.bat` na sua Área de Trabalho. Pode fechar o PowerShell.
4. Vá na Área de Trabalho e dê **dois cliques** nesse arquivo.
   - Se aparecer um aviso azul "O Windows protegeu o computador" (SmartScreen), clique em **"Mais informações"** → **"Executar assim mesmo"**. É normal em scripts baixados da internet.
5. Aguarde a janela preta instalar tudo sozinha (Python, dependências, etc.) — pode demorar alguns minutos na primeira vez.
6. Quando aparecer `Uvicorn server started` e `Local URL: http://localhost:8501` na janela preta, abra o navegador e acesse **http://localhost:8501**
   *(Não feche a janela preta — ela precisa ficar aberta enquanto você usa o programa.)*

## Captura de log do POS (ADB)

1. Conecte o POS ao computador por cabo USB.
2. No POS: **Configurações → Sobre o dispositivo** → toque 7x em "Número da versão" (ativa o modo desenvolvedor).
3. Volte e entre em **Opções do desenvolvedor** → ative **"Depuração USB"**.
4. Autorize quando aparecer o aviso na tela do POS.
5. No app, clique em **"🔄 Detectar Dispositivo"** na barra lateral.

> A captura de log só funciona rodando o app localmente (como acima). Uma versão publicada na web não tem acesso ao USB do seu computador.

## Usar de novo depois da primeira vez

Não precisa repetir o passo do PowerShell. Só dar dois cliques no mesmo `instalar_e_rodar.bat` que já está na Área de Trabalho — ele sempre baixa a versão mais atual sozinho e mantém seus testes salvos e logs já capturados.

---

Qualquer erro ou tela travada, entre em contato.
