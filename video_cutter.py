import os
import time
from moviepy import VideoFileClip, concatenate_videoclips
from proglog import ProgressBarLogger
import math
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

class VideoCutter:
    def __init__(self, video_path, output_dir="output"):
        self.video_path = video_path
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    def cut_scenes(self, scenes_dict, fps_original, bitrate="5000k", mode="Ambos", max_duration=50.0, num_photos=5, hw_accel="CPU", preview_mode="Total", progress_callback=None, frame_callback=None, cancel_event=None, log_callback=None):
        def _log(msg):
            if log_callback:
                log_callback(msg)
                
        stats = {
            "video_render_time": 0.0,
            "image_export_time": 0.0,
            "photo_extraction_time": 0.0,
            "processed_persons": 0,
            "photos_exported": 0
        }
        base_clip = VideoFileClip(self.video_path)
        original_w, original_h = base_clip.size
        
        target_aspect = 9 / 16
        target_h = original_h
        target_w = int(target_h * target_aspect)
        
        if target_w > original_w:
            target_w = original_w
            target_h = int(target_w / target_aspect)
            
        total_persons = len(scenes_dict)
        processed_persons = 0
        
        mp_pose = mp.solutions.pose
        
        # Iniciar o Curador IA (se a pasta referencias_ideais existir e tiver fotos, ele carregará o CLIP)
        ai_curator = None
        if mode in ["Ambos", "Apenas Imagens"]:
            ai_curator = AICurator(log_callback=log_callback)
            
        import threading
        stats_lock = threading.Lock()
        
        with mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5) as pose:
            def process_person_task(person_name, scenes):
                if cancel_event and cancel_event.is_set(): return
                base_clip_local = VideoFileClip(self.video_path)
                if cancel_event and cancel_event.is_set():
                    return
                    
                person_dir = os.path.join(self.output_dir, person_name)
                if not os.path.exists(person_dir):
                    os.makedirs(person_dir)
                    
                person_clips = []
                
                # Fotógrafo IA: Variáveis
                photo_candidates = [] # Armazenará as fotos
                global_photo_clock = [0.0]
                    
                for idx, scene in enumerate(scenes):
                    if cancel_event and cancel_event.is_set():
                        break
                        
                    start_time = scene['start_frame'] / fps_original
                    end_time = scene['end_frame'] / fps_original
                    
                    subclip = base_clip_local.subclipped(start_time, end_time)
                    
                    def make_crop_func(positions_smooth, start_f):
                        def crop_func(get_frame, t):
                            if cancel_event and cancel_event.is_set():
                                raise RuntimeError("Processamento cancelado pelo usuario")
                            frame = get_frame(t)
                            f_idx = int(t * fps_original) + start_f
                            if f_idx in positions_smooth:
                                cx, cy = positions_smooth[f_idx]
                            else:
                                keys = list(positions_smooth.keys())
                                if not keys: return frame
                                closest_f = min(keys, key=lambda k: abs(k - f_idx))
                                cx, cy = positions_smooth[closest_f]
                                
                            x1 = cx - (target_w // 2)
                            y1 = cy - (target_h // 2)
                            
                            x1 = max(0, min(x1, original_w - target_w))
                            y1 = max(0, min(y1, original_h - target_h))
                            
                            x2 = x1 + target_w
                            y2 = y1 + target_h
                            cropped = np.ascontiguousarray(frame[y1:y2, x1:x2])
                            
                            def evaluate_photo(cropped_img, time_or_frame, exact_t, coords):
                                sharpness = get_sharpness(cropped_img)
                                results = pose.process(cropped_img)
                                pose_score = 0
                                similarity_score = 0
                                
                                cut_detected = False
                                full_body_bonus = 0
                                
                                if results.pose_landmarks:
                                    landmarks = results.pose_landmarks.landmark
                                    
                                    # 1. Anti-Crop Estrito: Verificar se alguma parte visível encosta nas bordas (0.02 ou 0.98)
                                    for lm in landmarks:
                                        if lm.visibility > 0.5:
                                            if lm.x < 0.02 or lm.x > 0.98 or lm.y < 0.02 or lm.y > 0.98:
                                                cut_detected = True
                                                break
                                                
                                    # 2. Bônus de Corpo Inteiro: Verificar quadril, joelhos e calcanhares
                                    lower_body = [
                                        mp_pose.PoseLandmark.LEFT_HIP, mp_pose.PoseLandmark.RIGHT_HIP,
                                        mp_pose.PoseLandmark.LEFT_KNEE, mp_pose.PoseLandmark.RIGHT_KNEE
                                    ]
                                    if sum(1 for p in lower_body if landmarks[p.value].visibility > 0.5) >= 3:
                                        full_body_bonus = 1500
                                        
                                    # 3. Visibilidade básica dos braços
                                    arms = [mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.RIGHT_ELBOW]
                                    visible_arms = sum(1 for p in arms if landmarks[p.value].visibility > 0.5)
                                    pose_score = visible_arms * 250
                                
                                # Otimização de Performance: Só rodar a IA Curadora (CLIP) se o frame for pelo menos decente
                                if ai_curator and ai_curator.is_ready and not cut_detected and sharpness > 100:
                                    similarity_score = ai_curator.calculate_similarity(cropped_img)
                                
                                weighted_sharpness = sharpness * 5
                                final_score = weighted_sharpness + pose_score + similarity_score + full_body_bonus
                                
                                if cut_detected:
                                    final_score -= 5000
                                    _log(f"[IA] Avaliação {time_or_frame}: Rejeitado (Pessoa cortada nas bordas).")
                                elif sharpness < 100:
                                    final_score -= 5000
                                    _log(f"[IA] Avaliação {time_or_frame}: Rejeitado (Desfocado, Nitidez: {int(sharpness)}).")
                                else:
                                    msg = f"[IA] Avaliação {time_or_frame}: Aprovado (Nitidez: {int(sharpness)}"
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
                            
                            # O Fotógrafo entra em ação (Apenas se o modo permitir fotos)
                            if mode == "Ambos":
                                global_photo_clock[0] += (1.0 / fps_original)
                                if global_photo_clock[0] >= 0.5:
                                    evaluate_photo(cropped, f"Frame", global_t, (x1, y1, x2, y2))
                                    global_photo_clock[0] = 0.0
                                    
                            elif mode == "Apenas Imagens":
                                # Modo de altíssima performance
                                evaluate_photo(cropped, f"Amostra", global_t, (x1, y1, x2, y2))
                            
                            if frame_callback and preview_mode != "Desligado":
                                if preview_mode == "Total" or (preview_mode == "Metade" and f_idx % 2 == 0) or (preview_mode == "1/4" and f_idx % 4 == 0):
                                    frame_callback(cropped)
                            return cropped
                        return crop_func
                    
                    cropped_clip = subclip.transform(make_crop_func(scene['positions_smooth'], scene['start_frame']))
                    person_clips.append(cropped_clip)
                    
                if cancel_event and cancel_event.is_set():
                    return
                    
                if person_clips:
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
                        
                        # Eliminar pedaços com menos de 5 segundos
                        if part_clip.duration < 5.0:
                            continue
                            
                        if total_parts > 1:
                            output_filename = os.path.join(person_dir, f"{person_name}_Parte{valid_part_idx}.mp4")
                        else:
                            output_filename = os.path.join(person_dir, f"{person_name}_Completo.mp4")
                            
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
                            # Processa o vídeo de forma otimizada pulando frames desnecessários (2 frames por segundo)
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
                                photo_filename = os.path.join(fotos_dir, f"{person_name}_photo{idx+1}.jpg")
                                Image.fromarray(raw_cropped).save(photo_filename, "JPEG", quality=100, subsampling=0)
                                
                        cap.release()
                        with stats_lock:
                            stats["photo_extraction_time"] += (time.time() - t_start_photo)
                        with stats_lock:
                            stats["image_export_time"] += (time.time() - t_start_photo)
                    
                with stats_lock:
                    stats["processed_persons"] += 1
                if progress_callback:
                    progress_callback(stats["processed_persons"], total_persons)
                    
            import concurrent.futures
            import threading
            
            # stats_lock was already defined at top of cut_scenes
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 4) - 1)) as executor:
                futures = [executor.submit(process_person_task, name, sc) for name, sc in scenes_dict.items()]
                concurrent.futures.wait(futures)
                
            base_clip.close()
            
        return stats
