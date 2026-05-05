import webview
import time

class EspiaoAPI:
    def __init__(self):
        self.html_salvo = False

    def salvar_codigo_fonte(self, html_content):
        with open('flow_codigo_fonte.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("Código fonte salvo em flow_codigo_fonte.html!")
        self.html_salvo = True

def injetar_espião(janela):
    """
    Função rodada em background logo que a janela abre.
    """
    print("Modo Espião Iniciado! Aguardando carregamento...")
    # Aguarda um tempo pro usuário fazer login se necessário
    # E expõe uma função no console do navegador para capturar a tela.
    time.sleep(2)
    
    script = """
    // Cria um botão flutuante vermelho na tela para o usuário clicar quando quiser "espiar"
    let btn = document.createElement("button");
    btn.innerHTML = "🎯 CLIQUE AQUI PARA ESPIAR A PÁGINA";
    btn.style.position = "fixed";
    btn.style.top = "10px";
    btn.style.left = "50%";
    btn.style.transform = "translateX(-50%)";
    btn.style.zIndex = "999999";
    btn.style.padding = "15px 25px";
    btn.style.backgroundColor = "red";
    btn.style.color = "white";
    btn.style.fontWeight = "bold";
    btn.style.border = "none";
    btn.style.borderRadius = "8px";
    btn.style.cursor = "pointer";
    
    btn.onclick = function() {
        btn.innerHTML = "ESPIANDO...";
        // Chama a função Python passando o HTML inteiro do Labs!
        pywebview.api.salvar_codigo_fonte(document.documentElement.innerHTML).then(function() {
            btn.innerHTML = "HTML SALVO COM SUCESSO!";
            btn.style.backgroundColor = "green";
        });
    };
    
    document.body.appendChild(btn);
    """
    try:
        janela.evaluate_js(script)
    except Exception as e:
        print("Erro ao injetar espião, a página pode ter redirecionado:", e)

def abrir_navegador_flow():
    """Inicia a janela do pywebview"""
    api = EspiaoAPI()
    
    # Criamos a janela apontando pro Google Labs Flow
    janela = webview.create_window(
        title='Auto-Cutter Pro - Navegador Flow (Modo Espião)',
        url='https://labs.google/fx/pt/tools/flow',
        width=1280,
        height=800,
        js_api=api
    )
    
    # Iniciamos com debug=True para permitir o F12 (Inspecionar)
    webview.start(func=injetar_espião, args=(janela,), debug=True)

if __name__ == '__main__':
    abrir_navegador_flow()
