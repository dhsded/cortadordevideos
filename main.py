import multiprocessing
import os
import sys
import threading
import time
import subprocess

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def start_flask():
    """Inicia o servidor Flask em uma thread separada."""
    # Adicionar o diretório raiz ao path para importações
    root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root)
    
    # Importar e iniciar o Flask
    from server.app import app
    app.run(port=5000, debug=False, threaded=True, use_reloader=False)

def wait_for_server(port=5000, timeout=15):
    """Aguarda o Flask iniciar antes de abrir o PyWebView."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/")
            return True
        except Exception:
            time.sleep(0.2)
    return False

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Iniciar Flask em background
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Aguardar servidor
    print("Iniciando servidor...")
    ready = wait_for_server()
    if not ready:
        print("Erro: servidor não iniciou a tempo.")
        sys.exit(1)

    print("Servidor pronto. Abrindo interface...")

    # Abrir janela PyWebView
    import webview
    webview.create_window(
        title="Auto-Cutter Pro",
        url="http://localhost:5000",
        width=1280,
        height=800,
        min_size=(900, 600),
        background_color="#0A0A0F",
        frameless=False,
    )
    webview.start(debug=False)
