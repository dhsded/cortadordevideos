import os
from moviepy import VideoFileClip, concatenate_videoclips
import math

class VideoCutter:
    def __init__(self, video_path, output_dir="output"):
        self.video_path = video_path
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    def cut_scenes(self, scenes_dict, fps_original, bitrate="5000k", progress_callback=None, frame_callback=None, cancel_event=None):
        """
        Recebe um dicionário {person_name: [scene1, scene2, ...]}
        """
        # Carregar o vídeo base
        base_clip = VideoFileClip(self.video_path)
        original_w, original_h = base_clip.size
        
        # O aspect ratio de 9:16
        target_aspect = 9 / 16
        target_h = original_h
        target_w = int(target_h * target_aspect)
        
        # Garantir que a largura do crop não seja maior que a do vídeo
        if target_w > original_w:
            target_w = original_w
            target_h = int(target_w / target_aspect)
            
        total_persons = len(scenes_dict)
        processed_persons = 0
            
        for person_name, scenes in scenes_dict.items():
            if cancel_event and cancel_event.is_set():
                break
                
            person_dir = os.path.join(self.output_dir, person_name)
            if not os.path.exists(person_dir):
                os.makedirs(person_dir)
                
            person_clips = []
                
            for idx, scene in enumerate(scenes):
                if cancel_event and cancel_event.is_set():
                    break
                    
                start_time = scene['start_frame'] / fps_original
                end_time = scene['end_frame'] / fps_original
                
                # Cortar o tempo
                subclip = base_clip.subclipped(start_time, end_time)
                
                # Função de crop dinâmico (auto-reframe)
                def make_crop_func(positions_smooth, start_f):
                    def crop_func(get_frame, t):
                        if cancel_event and cancel_event.is_set():
                            raise RuntimeError("Processamento cancelado pelo usuario")
                        frame = get_frame(t)
                        
                        # Frame atual absoluto
                        f_idx = int(t * fps_original) + start_f
                        
                        # Pegar X,Y suavizado (ou o mais próximo se sair um pouco do limite)
                        if f_idx in positions_smooth:
                            cx, cy = positions_smooth[f_idx]
                        else:
                            # Se não achar o frame exato, pega o primeiro conhecido
                            keys = list(positions_smooth.keys())
                            if not keys:
                                return frame
                            closest_f = min(keys, key=lambda k: abs(k - f_idx))
                            cx, cy = positions_smooth[closest_f]
                            
                        # Calcular as bordas do crop (centralizado no X, Y)
                        x1 = cx - (target_w // 2)
                        y1 = cy - (target_h // 2)
                        
                        # Garantir que o crop não saia para fora do vídeo original
                        x1 = max(0, min(x1, original_w - target_w))
                        y1 = max(0, min(y1, original_h - target_h))
                        
                        x2 = x1 + target_w
                        y2 = y1 + target_h
                        
                        cropped = frame[y1:y2, x1:x2]
                        
                        if frame_callback:
                            frame_callback(cropped)
                            
                        return cropped
                    return crop_func
                
                # Aplicar a transformação no clip
                cropped_clip = subclip.transform(make_crop_func(scene['positions_smooth'], scene['start_frame']))
                person_clips.append(cropped_clip)
                
            if cancel_event and cancel_event.is_set():
                break
                
            if person_clips:
                # Magia da Fusão: Junta todos os clipes dessa pessoa em um só!
                final_clip = concatenate_videoclips(person_clips)
                output_filename = os.path.join(person_dir, f"{person_name}_Completo.mp4")
                
                try:
                    # Renderizar o vídeo inteiro unificado
                    final_clip.write_videofile(
                        output_filename, 
                        codec="libx264", 
                        audio_codec="aac",
                        bitrate=bitrate,
                        logger=None # Desabilitar o output do moviepy no terminal
                    )
                except RuntimeError as e:
                    if "cancelado" in str(e).lower():
                        break
                    else:
                        raise e
                finally:
                    final_clip.close()
                    for c in person_clips:
                        c.close()
                
            processed_persons += 1
            if progress_callback:
                progress_callback(processed_persons, total_persons)
                
        base_clip.close()
