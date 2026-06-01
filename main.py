import multiprocessing
import os
import sys
import threading
import time
import webbrowser

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def start_flask():
    """Inicia o servidor Flask em uma thread separada."""
    root = resource_path(".")
    sys.path.insert(0, root)

    # Redirecionar stderr para um arquivo de log para capturar erros
    log_path = os.path.join(os.path.dirname(sys.executable
                            if getattr(sys, 'frozen', False) else __file__),
                            "autocutter_log.txt")
    try:
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)  # Suprimir logs verbosos do Flask

        # Adicionar o diretório _MEIPASS ao sys.path para o server encontrar os módulos
        meipass = resource_path(".")
        if meipass not in sys.path:
            sys.path.insert(0, meipass)

        from server.app import app
        app.run(host="127.0.0.1", port=5000, debug=False,
                threaded=True, use_reloader=False)
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            import traceback
            f.write(f"\n[{time.strftime('%H:%M:%S')}] Erro Flask:\n{traceback.format_exc()}\n")

def wait_for_server(port=5000, timeout=20):
    """Aguarda o Flask iniciar antes de abrir o navegador."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Iniciar Flask em background
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Aguardar servidor estar pronto
    ready = wait_for_server()

    if ready:
        # Abrir no navegador padrão
        webbrowser.open("http://127.0.0.1:5000")
    else:
        # Tentar mesmo assim
        webbrowser.open("http://127.0.0.1:5000")

    # Manter o processo vivo enquanto o usuário usa o app
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
