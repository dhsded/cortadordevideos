import os
import time
import concurrent.futures
import threading
from moviepy import VideoFileClip, concatenate_videoclips
from proglog import ProgressBarLogger
import cv2
import numpy as np
from PIL import Image
import mediapipe as mp
from ai_curator import AICurator

class UILogger(ProgressBarLogger):
    def __init__(self, ui_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui_callback = ui_callback
        self.last_percent = -1

    def bars_callback(self, bar, attr, value, old_value=None):
        if attr == 'index':
            stats = self.bars[bar]
            if stats['total'] > 0:
                percent = int((stats['index'] / stats['total']) * 100)
                if percent != self.last_percent:
                    self.last_percent = percent
                    self.ui_callback(percent)

def get_sharpness(img):
    """Calcula a Variância Laplaciana para medir o quão nítida/focada está a imagem."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def _apply_lazy_pan(positions_smooth, lerp_factor=0.06):
    """
    Converte rastreamento direto em movimento de câmera gradual estilo CapCut.

    Em vez de seguir a pessoa frame-a-frame (causando pans bruscos),
    a câmera 'persegue' a pessoa com inércia (sistema de mola amortecida).

    lerp_factor=0.06 (6% por frame):
      - 50% do caminho em ~11 frames  (~0.37s a 30fps)
      -  90% do caminho em ~37 frames (~1.23s a 30fps)

    Resultado: pan cinematográfico onde a pessoa pode entrar pelo canto do
    frame e deslizar suavemente para o centro, sem cortes abruptos.
    """
    if not positions_smooth or len(positions_smooth) < 2:
        return positions_smooth

    frames = sorted(positions_smooth.keys())
    lazy = {}

    # Iniciar câmera na posição do primeiro frame detectado
    first_x, first_y = positions_smooth[frames[0]]
    cam_x, cam_y = float(first_x), float(first_y)

    for f in frames:
        tx, ty = positions_smooth[f]
        # EMA: aproxima a câmera do alvo em lerp_factor por frame
        cam_x += (tx - cam_x) * lerp_factor
        cam_y += (ty - cam_y) * lerp_factor
        lazy[f] = (int(cam_x), int(cam_y))

    return lazy

class VideoCutter:
    def __init__(self, video_path, output_dir="output"):
        self.video_path = video_path
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def cut_scenes(self, scenes_dict, fps_original, bitrate="5000k", mode="Ambos",
                   max_duration=50.0, min_duration=8.0, num_photos=5, hw_accel="CPU",
                   preview_mode="Total", progress_callback=None, frame_callback=None,
                   cancel_event=None, log_callback=None, global_person_counter=None,
                   counter_lock=None):

        def _log(msg):
            if log_callback:
                log_callback(msg)

        stats = {
            "video_render_time": 0.0,
            "image_export_time": 0.0,
            "photo_extraction_time": 0.0,
            "processed_persons": 0,
            "photos_exported": 0,
            "videos_cut": 0,
        }

        # Contador global de pessoas (compartilhado entre vídeos da fila)
        if global_person_counter is None:
            global_person_counter = [0]
        if counter_lock is None:
            counter_lock = threading.Lock()

        base_clip = VideoFileClip(self.video_path)
        original_w, original_h = base_clip.size

        # Detecção automática: vídeo já é retrato (9:16 ou similar)?
        aspect_ratio = original_w / original_h
        is_portrait = aspect_ratio <= 0.65  # 9:16 = 0.5625; tolerância para vídeos tipo 9:18

        if is_portrait:
            _log(f"[Auto-Reframe] Vídeo já está em formato retrato ({original_w}x{original_h}, ratio={aspect_ratio:.2f}). Pulando crop — apenas recortando por pessoa.")
        else:
            _log(f"[Auto-Reframe] Modo paisagem detectado ({original_w}x{original_h}). Aplicando Auto-Reframe 9:16.")

        target_aspect = 9 / 16
        target_h = original_h
        target_w = int(target_h * target_aspect)

        if target_w > original_w:
            target_w = original_w
            target_h = int(target_w / target_aspect)

        total_persons = len(scenes_dict)
        mp_pose_module = mp.solutions.pose

        # Curador IA (opcional)
        ai_curator = None
        if mode in ["Ambos", "Apenas Imagens"]:
            ai_curator = AICurator(log_callback=log_callback)

        stats_lock = threading.Lock()

        # ── Tarefa por pessoa (cada thread tem o seu próprio mp_pose.Pose) ──────
        def process_person_task(person_name, scenes):
            if cancel_event and cancel_event.is_set():
                return

            # IMPORTANTE: cada thread cria seu próprio Pose para thread-safety
            # MediaPipe NÃO é thread-safe quando compartilhado entre threads
            with mp_pose_module.Pose(static_image_mode=False, min_detection_confidence=0.5) as pose:
                base_clip_local = VideoFileClip(self.video_path)
                if cancel_event and cancel_event.is_set():
                    base_clip_local.close()
                    return

                # Atribuir número global sequencial a esta pessoa
                with counter_lock:
                    global_person_counter[0] += 1
                    global_num = global_person_counter[0]

                display_name = f"Pessoa_{global_num:03d}"
                person_dir = os.path.join(self.output_dir, display_name)
                if not os.path.exists(person_dir):
                    os.makedirs(person_dir)

                person_clips = []

                # Fotógrafo IA: Variáveis
                photo_candidates = []
                global_photo_clock = [0.0]

                if is_portrait:
                    # Modo retrato: apenas recortar o subclip pelos timestamps, sem crop/reframe
                    _log(f"[{display_name} ({person_name})] Modo Retrato: {len(scenes)} cena(s) sem reframe.")
                    for idx, scene in enumerate(scenes):
                        if cancel_event and cancel_event.is_set():
                            break
                        start_time = scene['start_frame'] / fps_original
                        end_time = scene['end_frame'] / fps_original
                        _log(f"[{display_name}] Cena {idx+1}/{len(scenes)}: {start_time:.1f}s -> {end_time:.1f}s")
                        subclip = base_clip_local.subclipped(start_time, end_time)
                        person_clips.append(subclip)
                else:
                    _log(f"[{display_name} ({person_name})] Modo Paisagem: {len(scenes)} cena(s) com Auto-Reframe 9:16.")
                    for idx, scene in enumerate(scenes):
                        if cancel_event and cancel_event.is_set():
                            break

                        start_time = scene['start_frame'] / fps_original
                        end_time = scene['end_frame'] / fps_original
                        scene_dur = end_time - start_time
                        _log(f"[{display_name}] Cena {idx+1}/{len(scenes)}: {start_time:.1f}s -> {end_time:.1f}s ({scene_dur:.1f}s)")

                        subclip = base_clip_local.subclipped(start_time, end_time)

                        # Aplicar pan gradual (lazy camera): a câmera persegue
                        # a pessoa com inércia, como keyframes graduais do CapCut.
                        # A pessoa pode aparecer na borda do frame e deslizar
                        # suavemente para o centro sem cortes bruscos.
                        lazy_positions = _apply_lazy_pan(scene['positions_smooth'])

                        def make_crop_func(positions_smooth, start_f, end_f, _pose=pose):
                            def crop_func(get_frame, t):
                                if cancel_event and cancel_event.is_set():
                                    raise RuntimeError("Processamento cancelado pelo usuario")
                                frame = get_frame(t)
                                f_idx = int(t * fps_original) + start_f
                                if f_idx in positions_smooth:
                                    cx, cy = positions_smooth[f_idx]
                                else:
                                    if f_idx < start_f:
                                        cx, cy = positions_smooth.get(start_f, next(iter(positions_smooth.values())))
                                    else:
                                        cx, cy = positions_smooth.get(end_f, next(reversed(list(positions_smooth.values()))))

                                x1 = cx - (target_w // 2)
                                y1 = cy - int(target_h * 0.33)

                                x1 = max(0, min(x1, original_w - target_w))
                                y1 = max(0, min(y1, original_h - target_h))

                                x2 = x1 + target_w
                                y2 = y1 + target_h
                                cropped = np.ascontiguousarray(frame[y1:y2, x1:x2])

                                def evaluate_photo(cropped_img, time_or_frame, exact_t, coords):
                                    sharpness = get_sharpness(cropped_img)
                                    results = _pose.process(cropped_img)
                                    pose_score = 0
                                    similarity_score = 0
                                    cut_detected = False
                                    full_body_bonus = 0

                                    if results.pose_landmarks:
                                        landmarks = results.pose_landmarks.landmark
                                        for lm in landmarks:
                                            if lm.visibility > 0.5:
                                                if lm.x < 0.02 or lm.x > 0.98 or lm.y < 0.02 or lm.y > 0.98:
                                                    cut_detected = True
                                                    break
                                        lower_body = [
                                            mp_pose_module.PoseLandmark.LEFT_HIP, mp_pose_module.PoseLandmark.RIGHT_HIP,
                                            mp_pose_module.PoseLandmark.LEFT_KNEE, mp_pose_module.PoseLandmark.RIGHT_KNEE
                                        ]
                                        if sum(1 for p in lower_body if landmarks[p.value].visibility > 0.5) >= 3:
                                            full_body_bonus = 1500
                                        arms = [mp_pose_module.PoseLandmark.LEFT_SHOULDER, mp_pose_module.PoseLandmark.RIGHT_SHOULDER,
                                                mp_pose_module.PoseLandmark.LEFT_ELBOW, mp_pose_module.PoseLandmark.RIGHT_ELBOW]
                                        visible_arms = sum(1 for p in arms if landmarks[p.value].visibility > 0.5)
                                        pose_score = visible_arms * 250

                                    if ai_curator and ai_curator.is_ready and not cut_detected and sharpness > 100:
                                        similarity_score = ai_curator.calculate_similarity(cropped_img)

                                    weighted_sharpness = sharpness * 5
                                    final_score = weighted_sharpness + pose_score + similarity_score + full_body_bonus

                                    if cut_detected:
                                        final_score -= 5000
                                    elif sharpness < 100:
                                        final_score -= 5000
                                    else:
                                        msg = f"[IA] Avaliacao {time_or_frame}: Aprovado (Nitidez: {int(sharpness)}"
                                        if full_body_bonus > 0:
                                            msg += " | Corpo Inteiro"
                                        if similarity_score > 0:
                                            msg += f" | CLIP: {int(similarity_score)}"
                                        msg += f" | Final: {int(final_score)})"
                                        _log(msg)

                                    photo_candidates.append((final_score, exact_t, coords[0], coords[1], coords[2], coords[3]))
                                    photo_candidates.sort(key=lambda x: x[0], reverse=True)
                                    if len(photo_candidates) > num_photos:
                                        photo_candidates.pop()

                                global_t = f_idx / fps_original

                                if mode == "Ambos":
                                    global_photo_clock[0] += (1.0 / fps_original)
                                    if global_photo_clock[0] >= 0.5:
                                        evaluate_photo(cropped, "Frame", global_t, (x1, y1, x2, y2))
                                        global_photo_clock[0] = 0.0
                                elif mode == "Apenas Imagens":
                                    evaluate_photo(cropped, "Amostra", global_t, (x1, y1, x2, y2))

                                if frame_callback and preview_mode != "Desligado":
                                    if (preview_mode == "Total" or
                                        (preview_mode == "Metade" and f_idx % 2 == 0) or
                                        (preview_mode == "1/4" and f_idx % 4 == 0)):
                                        frame_callback(cropped)
                                return cropped
                            return crop_func

                        cropped_clip = subclip.transform(make_crop_func(lazy_positions, scene['start_frame'], scene['end_frame']))
                        person_clips.append(cropped_clip)

                if cancel_event and cancel_event.is_set():
                    base_clip_local.close()
                    return

                if person_clips:
                    _log(f"[{display_name}] Concatenando {len(person_clips)} cena(s)...")
                    final_clip = concatenate_videoclips(person_clips)

                    # CHUNKING (Divisão Automática baseada no max_duration)
                    durations = []
                    total_duration = final_clip.duration
                    current_time = 0.0
                    while current_time < total_duration:
                        next_time = min(current_time + max_duration, total_duration)
                        durations.append((current_time, next_time))
                        current_time = next_time

                    total_parts = len(durations)
                    valid_part_idx = 1

                    t_start_render = time.time()
                    for st, et in durations:
                        if cancel_event and cancel_event.is_set():
                            break

                        part_clip = final_clip.subclipped(st, et)

                        # Se o vídeo tiver menos que min_duration, aplicar câmera lenta
                        if part_clip.duration < min_duration:
                            if part_clip.duration <= 0.3:
                                _log(f"[{person_name}] Parte {valid_part_idx} ignorada (muito curta: {part_clip.duration:.1f}s — mínimo 0.3s).")
                                continue
                            import moviepy.video.fx as vfx
                            factor = part_clip.duration / min_duration
                            slow_pct = int(factor * 100)
                            _log(f"[{person_name}] 🐢 Clip curto ({part_clip.duration:.1f}s) → slow motion {slow_pct}% → {min_duration:.0f}s finais.")
                            part_clip = part_clip.with_effects([vfx.MultiplySpeed(factor)]).without_audio()

                        _log(f"[{display_name}] Renderizando parte {valid_part_idx} ({part_clip.duration:.1f}s)...")

                        if total_parts > 1:
                            output_filename = os.path.join(person_dir, f"{display_name}_Parte{valid_part_idx}.mp4")
                        else:
                            output_filename = os.path.join(person_dir, f"{display_name}_Completo.mp4")

                        if mode in ["Ambos", "Apenas Vídeo"]:
                            def update_render_progress(percent):
                                if progress_callback:
                                    progress_callback(percent, 100)

                            ui_logger = UILogger(update_render_progress)
                            codec_map = {
                                "CPU": "libx264",
                                "NVIDIA": "h264_nvenc",
                                "AMD": "h264_amf",
                                "Intel": "h264_qsv"
                            }
                            selected_codec = codec_map.get(hw_accel, "libx264")
                            try:
                                part_clip.write_videofile(
                                    output_filename,
                                    codec=selected_codec,
                                    audio_codec="aac",
                                    bitrate=bitrate,
                                    logger=ui_logger
                                )
                            except RuntimeError as e:
                                if "cancelado" in str(e).lower():
                                    break
                                else:
                                    raise e

                        elif mode == "Apenas Imagens":
                            t_step = 0.5
                            total_evals = int(part_clip.duration / t_step)
                            for i, t in enumerate(np.arange(0, part_clip.duration, t_step)):
                                if cancel_event and cancel_event.is_set():
                                    break
                                _ = part_clip.get_frame(t)
                                if progress_callback and total_evals > 0:
                                    percent = int((i / total_evals) * 100)
                                    progress_callback(percent, 100)

                        valid_part_idx += 1
                        part_clip.close()

                    _log(f"[{person_name}] Renderizacao concluida! {valid_part_idx - 1} arquivo(s) gerado(s).")
                    with stats_lock:
                        stats["video_render_time"] += (time.time() - t_start_render)

                    final_clip.close()
                    for c in person_clips:
                        c.close()

                    # FOTÓGRAFO IA: Exportar as fotos com Qualidade Máxima (Raw)
                    if mode in ["Ambos", "Apenas Imagens"] and photo_candidates:
                        t_start_photo = time.time()
                        fotos_dir = os.path.join(person_dir, "fotos")
                        if not os.path.exists(fotos_dir):
                            os.makedirs(fotos_dir)
                        _log(f"[IA] Extraindo {len(photo_candidates[:num_photos])} fotos em qualidade RAW 100% (OpenCV)...")
                        cap = cv2.VideoCapture(self.video_path)
                        for idx, (score, global_t, x1, y1, x2, y2) in enumerate(photo_candidates[:num_photos]):
                            cap.set(cv2.CAP_PROP_POS_MSEC, global_t * 1000)
                            ret, frame_bgr = cap.read()
                            if ret:
                                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                                raw_cropped = np.ascontiguousarray(frame_rgb[y1:y2, x1:x2])
                                photo_filename = os.path.join(fotos_dir, f"{display_name}_photo{idx+1}.jpg")
                                Image.fromarray(raw_cropped).save(photo_filename, "JPEG", quality=100, subsampling=0)
                        cap.release()
                        with stats_lock:
                            stats["photo_extraction_time"] += (time.time() - t_start_photo)
                            stats["image_export_time"] += (time.time() - t_start_photo)

                with stats_lock:
                    stats["processed_persons"] += 1
                    stats["videos_cut"] += (valid_part_idx - 1) if person_clips else 0
                if progress_callback:
                    progress_callback(stats["processed_persons"], total_persons)

                base_clip_local.close()

        # ── Executar todas as pessoas em paralelo ────────────────────────────
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 4) - 1)) as executor:
            futures = [executor.submit(process_person_task, name, sc) for name, sc in scenes_dict.items()]
            concurrent.futures.wait(futures)

        base_clip.close()
        return stats
