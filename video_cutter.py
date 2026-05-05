import os
from moviepy import VideoFileClip, concatenate_videoclips
from proglog import ProgressBarLogger
import math
import cv2
from PIL import Image

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
            
    def cut_scenes(self, scenes_dict, fps_original, bitrate="5000k", progress_callback=None, frame_callback=None, cancel_event=None):
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
        
        # Max duration in seconds (Requisito: no máximo 50s)
        max_duration = 50.0
            
        for person_name, scenes in scenes_dict.items():
            if cancel_event and cancel_event.is_set():
                break
                
            person_dir = os.path.join(self.output_dir, person_name)
            if not os.path.exists(person_dir):
                os.makedirs(person_dir)
                
            person_clips = []
            
            # Fotógrafo IA: Variáveis
            photo_candidates = [] # Armazenará o TOP 5 fotos da pessoa (para economizar RAM)
            global_photo_clock = [0.0]
                
            for idx, scene in enumerate(scenes):
                if cancel_event and cancel_event.is_set():
                    break
                    
                start_time = scene['start_frame'] / fps_original
                end_time = scene['end_frame'] / fps_original
                
                subclip = base_clip.subclipped(start_time, end_time)
                
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
                        cropped = frame[y1:y2, x1:x2]
                        
                        # O Fotógrafo entra em ação! A cada 0.5s contínuos
                        global_photo_clock[0] += (1.0 / fps_original)
                        if global_photo_clock[0] >= 0.5:
                            score = get_sharpness(cropped)
                            photo_candidates.append((score, cropped.copy()))
                            # Manter apenas as 5 mais nítidas na memória para economizar recursos pesados
                            photo_candidates.sort(key=lambda x: x[0], reverse=True)
                            if len(photo_candidates) > 5:
                                photo_candidates.pop()
                            global_photo_clock[0] = 0.0
                        
                        if frame_callback:
                            frame_callback(cropped)
                        return cropped
                    return crop_func
                
                cropped_clip = subclip.transform(make_crop_func(scene['positions_smooth'], scene['start_frame']))
                person_clips.append(cropped_clip)
                
            if cancel_event and cancel_event.is_set():
                break
                
            if person_clips:
                final_clip = concatenate_videoclips(person_clips)
                
                # CHUNKING (Divisão Automática de 50s)
                durations = []
                total_duration = final_clip.duration
                current_time = 0.0
                while current_time < total_duration:
                    next_time = min(current_time + max_duration, total_duration)
                    durations.append((current_time, next_time))
                    current_time = next_time
                    
                total_parts = len(durations)
                
                for part_idx, (st, et) in enumerate(durations):
                    if cancel_event and cancel_event.is_set():
                        break
                        
                    part_clip = final_clip.subclipped(st, et)
                    if total_parts > 1:
                        output_filename = os.path.join(person_dir, f"{person_name}_Parte{part_idx+1}.mp4")
                    else:
                        output_filename = os.path.join(person_dir, f"{person_name}_Completo.mp4")
                        
                    def update_render_progress(percent):
                        if progress_callback:
                            # Gambiarra genial para a interface entender que é porcentagem
                            progress_callback(percent, 100)
                            
                    ui_logger = UILogger(update_render_progress)
                    
                    try:
                        part_clip.write_videofile(
                            output_filename, 
                            codec="libx264", 
                            audio_codec="aac",
                            bitrate=bitrate,
                            logger=ui_logger
                        )
                    except RuntimeError as e:
                        if "cancelado" in str(e).lower():
                            break
                        else:
                            raise e
                    finally:
                        part_clip.close()
                
                final_clip.close()
                for c in person_clips:
                    c.close()
                
                # FOTÓGRAFO IA: Exportar as fotos!
                if photo_candidates:
                    fotos_dir = os.path.join(person_dir, "fotos")
                    if not os.path.exists(fotos_dir):
                        os.makedirs(fotos_dir)
                    for photo_idx, (score, img_array) in enumerate(photo_candidates):
                        img_pil = Image.fromarray(img_array)
                        foto_path = os.path.join(fotos_dir, f"Foto_{photo_idx+1}.jpg")
                        img_pil.save(foto_path, quality=95)
                
            processed_persons += 1
            if progress_callback:
                progress_callback(processed_persons, total_persons)
                
        base_clip.close()
