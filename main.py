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
    log_path = os.path.join(
        os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__),
        "autocutter_log.txt"
    )
    try:
        import logging
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

        meipass = resource_path(".")
        if meipass not in sys.path:
            sys.path.insert(0, meipass)

        from server.app import app
        app.run(host="127.0.0.1", port=5000, debug=False,
                threaded=True, use_reloader=False)
    except Exception:
        import traceback
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%H:%M:%S')}] Erro Flask:\n{traceback.format_exc()}\n")

def wait_for_server(port=5000, timeout=20):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False

def open_app_window(url: str):
    """
    Abre o app em modo desktop (sem barra de endereço/abas) usando
    Edge ou Chrome com flag --app. Fallback para webbrowser se nenhum for encontrado.
    """
    BROWSER_PATHS = [
        # Microsoft Edge (pré-instalado no Windows 10/11)
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # Google Chrome
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # Brave
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]

    for path in BROWSER_PATHS:
        if os.path.exists(path):
            subprocess.Popen([
                path,
                f"--app={url}",
                "--window-size=1280,800",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
            ])
            return True

    # Último recurso: navegador padrão
    import webbrowser
    webbrowser.open(url)
    return False

if __name__ == "__main__":
    multiprocessing.freeze_support()

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    ready = wait_for_server()

    open_app_window("http://127.0.0.1:5000")

    # Manter o processo vivo enquanto o usuário usa o app
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
