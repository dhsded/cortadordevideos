import os, sys, json, queue, threading, time
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from tkinter import filedialog
import tkinter as tk

# ── Adicionar o root do projeto ao path ──────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from video_tracker import VideoTracker
from video_cutter  import VideoCutter

# ── Flask setup ──────────────────────────────────────────────────────────────
FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")

# ── Estado global do app ─────────────────────────────────────────────────────
state = {
    "video_queue":   [],          # list of absolute paths
    "output_dir":    None,
    "settings": {
        "mode":      "Ambos",
        "duration":  "50",
        "min_dur":   "8",
        "photos":    "5",
        "quality":   "Boa",
        "hw":        "CPU",
        "sound":     "Soft Bell",
        "precision": "Alta (a cada 5 frames)",
    },
    "processing":    False,
    "cancel_event":  threading.Event(),
}

# Fila de eventos SSE: cada item é um dict {"event": str, "data": any}
sse_queue: queue.Queue = queue.Queue()

def sse_push(event: str, data):
    sse_queue.put({"event": event, "data": data})

# ── Rotas estáticas ───────────────────────────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    full = os.path.join(FRONTEND_DIST, path)
    if path and os.path.exists(full):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")

# ── SSE Stream ────────────────────────────────────────────────────────────────
@app.route("/api/stream")
def stream():
    def generate():
        while True:
            try:
                item = sse_queue.get(timeout=25)
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})

# ── Queue endpoints ───────────────────────────────────────────────────────────
@app.route("/api/queue", methods=["GET"])
def get_queue():
    return jsonify(state["video_queue"])

@app.route("/api/queue/add", methods=["POST"])
def add_to_queue():
    paths = request.json.get("paths", [])
    added = []
    for p in paths:
        if p not in state["video_queue"]:
            state["video_queue"].append(p)
            added.append(p)
    return jsonify({"added": added, "queue": state["video_queue"]})

@app.route("/api/queue/remove", methods=["POST"])
def remove_from_queue():
    path = request.json.get("path")
    if path in state["video_queue"]:
        state["video_queue"].remove(path)
    return jsonify({"queue": state["video_queue"]})

@app.route("/api/queue/clear", methods=["POST"])
def clear_queue():
    state["video_queue"].clear()
    return jsonify({"queue": []})

# ── File dialog (precisa rodar na thread principal via tkinter oculto) ─────────
_tk_root = None

def _get_tk():
    global _tk_root
    if _tk_root is None:
        _tk_root = tk.Tk()
        _tk_root.withdraw()
    return _tk_root

@app.route("/api/dialog/videos", methods=["POST"])
def dialog_videos():
    result = {"paths": []}
    ev = threading.Event()
    def _open():
        paths = filedialog.askopenfilenames(
            parent=_get_tk(),
            title="Selecione vídeos para a fila",
            filetypes=[("Arquivos de Vídeo", "*.mp4 *.avi *.mov *.mkv *.MP4 *.AVI *.MOV *.MKV")]
        )
        result["paths"] = list(paths)
        ev.set()
    import webview
    # Se pywebview estiver rodando, precisamos de um workaround
    # Usamos uma thread separada para o diálogo
    t = threading.Thread(target=_open)
    t.start()
    t.join(timeout=60)
    return jsonify(result)

@app.route("/api/dialog/output", methods=["POST"])
def dialog_output():
    result = {"path": None}
    def _open():
        path = filedialog.askdirectory(parent=_get_tk(), title="Selecione a pasta de saída")
        result["path"] = path or None
        if path:
            state["output_dir"] = path
    t = threading.Thread(target=_open)
    t.start()
    t.join(timeout=60)
    return jsonify(result)

# ── Settings ──────────────────────────────────────────────────────────────────
@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(state["settings"])

@app.route("/api/settings", methods=["POST"])
def save_settings():
    state["settings"].update(request.json)
    return jsonify(state["settings"])

@app.route("/api/output", methods=["GET"])
def get_output():
    return jsonify({"output_dir": state["output_dir"]})

# ── Processamento ─────────────────────────────────────────────────────────────
@app.route("/api/process/start", methods=["POST"])
def start_processing():
    if state["processing"]:
        return jsonify({"error": "Já em andamento"}), 400
    state["cancel_event"].clear()
    t = threading.Thread(target=_run_pipeline, daemon=True)
    t.start()
    return jsonify({"started": True})

@app.route("/api/process/cancel", methods=["POST"])
def cancel_processing():
    state["cancel_event"].set()
    return jsonify({"cancelled": True})

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({"processing": state["processing"]})

def _run_pipeline():
    state["processing"] = True
    try:
        s = state["settings"]
        precision_map = {
            "Alta (a cada 5 frames)": 5,
            "Média (a cada 10 frames)": 10,
            "Rápida (a cada 15 frames)": 15,
        }
        quality_bitrate_map = {
            "Baixa": "1000k", "Média": "2500k", "Boa": "5000k",
            "Alta": "8000k", "Superior": "12000k"
        }
        sample_rate = precision_map.get(s["precision"], 5)
        bitrate     = quality_bitrate_map.get(s["quality"], "5000k")

        queue_snapshot        = list(state["video_queue"])
        total_videos          = len(queue_snapshot)
        global_person_counter = [0]
        counter_lock          = threading.Lock()

        accum = {
            "video_render_time": 0.0, "image_export_time": 0.0,
            "photo_extraction_time": 0.0, "processed_persons": 0,
            "photos_exported": 0, "videos_cut": 0,
            "total_persons_found": 0, "tracking_time": 0.0,
        }

        sse_push("started", {"total": total_videos})

        for vid_idx, video_path in enumerate(queue_snapshot):
            if state["cancel_event"].is_set():
                break

            vid_name = os.path.basename(video_path)
            sse_push("video_start", {"index": vid_idx, "total": total_videos,
                                      "name": vid_name, "path": video_path})

            def log(msg):
                sse_push("log", {"text": msg})

            def track_progress(current, total_f):
                sse_push("progress", {"current": current, "total": total_f,
                                       "phase": 1, "video": vid_name})

            def new_person_cb(name, face_rgb):
                import base64
                from PIL import Image
                import io
                img = Image.fromarray(face_rgb)
                img.thumbnail((80, 80))
                buf = io.BytesIO()
                img.save(buf, "JPEG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                sse_push("new_person", {"name": name, "image": b64})
                log(f"Nova pessoa: {name}")

            log(f"=== Vídeo {vid_idx+1}/{total_videos}: {vid_name} ===")

            tracker = VideoTracker(video_path, sample_rate=sample_rate)
            t0 = time.time()
            scenes, final_faces_rgb = tracker.process_video(
                preview_mode="Metade",
                progress_callback=track_progress,
                frame_callback=None,  # sem preview por ora (heavy)
                new_person_callback=new_person_cb,
                cancel_event=state["cancel_event"],
                log_callback=log,
            )
            t_phase1 = time.time() - t0

            if state["cancel_event"].is_set():
                sse_push("video_status", {"path": video_path, "status": "cancelled"})
                break

            if not scenes:
                log(f"Nenhuma pessoa em {vid_name}.")
                sse_push("video_status", {"path": video_path, "status": "no_persons"})
                continue

            n_persons = len(scenes)
            accum["total_persons_found"] += n_persons
            log(f"Fase 1: {t_phase1:.1f}s | {n_persons} pessoa(s)")
            sse_push("progress", {"current": 0, "total": 100, "phase": 2, "video": vid_name})

            final_output_dir = (state["output_dir"] or
                                os.path.join(os.path.dirname(video_path), "output_cortes"))

            cutter = VideoCutter(video_path, output_dir=final_output_dir)

            def cut_progress(current, total_p):
                sse_push("progress", {"current": current, "total": total_p,
                                       "phase": 2, "video": vid_name})

            st = cutter.cut_scenes(
                scenes, tracker.fps, bitrate=bitrate,
                mode=s["mode"],
                max_duration=float(s["duration"]),
                min_duration=float(s["min_dur"]),
                num_photos=int(s["photos"]),
                hw_accel=s["hw"],
                preview_mode="Desligado",
                progress_callback=cut_progress,
                cancel_event=state["cancel_event"],
                log_callback=log,
                global_person_counter=global_person_counter,
                counter_lock=counter_lock,
            )
            st["tracking_time"] = t_phase1

            for k in ["video_render_time", "image_export_time", "photo_extraction_time",
                       "processed_persons", "photos_exported", "videos_cut"]:
                accum[k] = accum.get(k, 0) + st.get(k, 0)
            accum["tracking_time"] += t_phase1

            status = "cancelled" if state["cancel_event"].is_set() else "done"
            sse_push("video_status", {"path": video_path, "status": status})
            sse_push("queue_progress", {"done": vid_idx + 1, "total": total_videos})

        accum["total_videos_processed"] = total_videos
        sse_push("done", accum)
        sse_push("log", {"text": f"🎉 Concluído! {accum['total_persons_found']} pessoas | {accum['videos_cut']} vídeos cortados"})

    except Exception as e:
        import traceback
        sse_push("error", {"message": str(e), "traceback": traceback.format_exc()})
    finally:
        state["processing"] = False


if __name__ == "__main__":
    app.run(port=5000, debug=False, threaded=True)
