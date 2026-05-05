import cv2
import face_recognition
import numpy as np
import os
from collections import defaultdict
from scipy.signal import savgol_filter

class VideoTracker:
    def __init__(self, video_path, sample_rate=1, tolerance=0.55):
        """
        video_path: caminho do vídeo
        sample_rate: analisar 1 a cada N frames
        tolerance: tolerância do face_recognition (menor = mais estrito, padrão 0.55)
        """
        self.video_path = video_path
        self.sample_rate = sample_rate
        self.tolerance = tolerance
        
        self.known_encodings = []
        self.known_names = []
        self.known_histograms = {} # name -> histogram
        self.person_encodings = defaultdict(list) # name -> todos os encodings daquela pessoa
        self.person_faces_rgb = {} # name -> imagem RGB do rosto (para a Galeria)
        
        # Estrutura: person_name -> list of (frame_index, center_x, center_y, box_size)
        self.tracking_data = defaultdict(list)
        
        # Info do vídeo
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.cap.release()

    def _calculate_iou(self, boxA, boxB):
        # box: (top, right, bottom, left)
        xA = max(boxA[3], boxB[3])
        yA = max(boxA[0], boxB[0])
        xB = min(boxA[1], boxB[1])
        yB = min(boxA[2], boxB[2])
        
        interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
        
        boxAArea = (boxA[1] - boxA[3] + 1) * (boxA[2] - boxA[0] + 1)
        boxBArea = (boxB[1] - boxB[3] + 1) * (boxB[2] - boxB[0] + 1)
        
        iou = interArea / float(boxAArea + boxBArea - interArea)
        return iou

    def _extract_torso_histogram(self, frame, face_box):
        top, right, bottom, left = face_box
        h, w, _ = frame.shape
        
        # Estimar o tronco (torso) abaixo do rosto
        face_height = bottom - top
        torso_top = bottom
        torso_bottom = min(h, bottom + int(face_height * 1.5))
        torso_left = max(0, left - int((right - left) * 0.5))
        torso_right = min(w, right + int((right - left) * 0.5))
        
        if torso_bottom <= torso_top or torso_right <= torso_left:
            return None
            
        torso_roi = frame[torso_top:torso_bottom, torso_left:torso_right]
        hsv_roi = cv2.cvtColor(torso_roi, cv2.COLOR_RGB2HSV)
        
        # Histograma 2D (Hue e Saturation) para ignorar sombras e focar nas cores reais da roupa
        hist = cv2.calcHist([hsv_roi], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    def process_video(self, progress_callback=None, frame_callback=None, new_person_callback=None, cancel_event=None):
        import mediapipe as mp
        # Importação explícita para o PyInstaller não se perder
        import mediapipe.python.solutions.face_detection as mp_face_detection_module
        mp_face_detection = mp.solutions.face_detection if hasattr(mp, 'solutions') else mp_face_detection_module
        
        cap = cv2.VideoCapture(self.video_path)
        frame_idx = 0
        
        last_frame_faces = [] # list of {'name': name, 'box': box}
        
        with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
            while True:
                if cancel_event and cancel_event.is_set():
                    break
                    
                ret, frame = cap.read()
                if not ret:
                    break
                    
                if frame_idx % self.sample_rate == 0:
                    # MediaPipe precisa de RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    results = face_detection.process(rgb_frame)
                    face_locations = []
                    
                    if results.detections:
                        ih, iw, _ = frame.shape
                        for detection in results.detections:
                            bboxC = detection.location_data.relative_bounding_box
                            # face_recognition usa (top, right, bottom, left)
                            x = int(bboxC.xmin * iw)
                            y = int(bboxC.ymin * ih)
                            w = int(bboxC.width * iw)
                            h = int(bboxC.height * ih)
                            
                            x = max(0, x)
                            y = max(0, y)
                            x_right = min(iw, x + w)
                            y_bottom = min(ih, y + h)
                            
                            if x_right > x and y_bottom > y:
                                face_locations.append((y, x_right, y_bottom, x))
                                
                        if face_locations:
                            # Filtro de Protagonistas: Ignorar rostos menores que 60% do tamanho do maior rosto do frame
                            max_box_size = max([max(r - l, b - t) for (t, r, b, l) in face_locations])
                            primary_face_locations = []
                            for loc in face_locations:
                                t, r, b, l = loc
                                box_size = max(r - l, b - t)
                                if box_size >= max_box_size * 0.6:
                                    primary_face_locations.append(loc)
                            face_locations = primary_face_locations
                    
                    if not face_locations:
                        last_frame_faces = [] # Perdeu todo mundo
                        if frame_callback:
                            frame_callback(rgb_frame)
                    else:
                        # num_jitters=2 para aumentar a precisão na extração de features
                        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=2)
                        
                        preview_frame = frame.copy() if frame_callback else None
                        current_frame_faces = []
                        
                        for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                            if preview_frame is not None:
                                cv2.rectangle(preview_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                            
                            center_x = (left + right) // 2
                            center_y = (top + bottom) // 2
                            box_size = max(right - left, bottom - top)
                            
                            name = "Desconhecido"
                            current_box = (top, right, bottom, left)
                            current_hist = self._extract_torso_histogram(rgb_frame, current_box)
                            
                            # CAMADA 1: Rastreamento Espacial (IoU - Física)
                            best_iou = 0
                            best_iou_name = None
                            for last_face in last_frame_faces:
                                iou = self._calculate_iou(current_box, last_face['box'])
                                if iou > best_iou:
                                    best_iou = iou
                                    best_iou_name = last_face['name']
                                    
                            if best_iou > 0.35: # Se a caixa sobrepõe pelo menos 35% com o frame anterior, é a mesma pessoa
                                name = best_iou_name
                                # Como ele pode ter virado o rosto, vamos salvar esse novo "perfil" na memória
                                self.known_encodings.append(encoding)
                                self.known_names.append(name)
                                self.person_encodings[name].append(encoding)
                                if current_hist is not None:
                                    self.known_histograms[name] = current_hist
                            
                            # CAMADA 2 e 3: Biometria e Roupas (se a pessoa se moveu muito rápido ou acabou de entrar)
                            if name == "Desconhecido" and self.known_encodings:
                                face_distances = face_recognition.face_distance(self.known_encodings, encoding)
                                best_match_index = np.argmin(face_distances)
                                distance = face_distances[best_match_index]
                                
                                if distance < self.tolerance:
                                    # Camada 2: Biometria exata (Rosto não mudou)
                                    name = self.known_names[best_match_index]
                                    if distance > 0.15: # Evita poluir a memória com frames idênticos
                                        self.known_encodings.append(encoding)
                                        self.known_names.append(name)
                                        self.person_encodings[name].append(encoding)
                                        
                                elif distance < 0.75 and current_hist is not None:
                                    # Camada 3: Biometria confusa, mas rosto parecido. Vamos olhar a ROUPA!
                                    candidate_name = self.known_names[best_match_index]
                                    if candidate_name in self.known_histograms and self.known_histograms[candidate_name] is not None:
                                        candidate_hist = self.known_histograms[candidate_name]
                                        # Compara os pixels
                                        hist_match = cv2.compareHist(current_hist, candidate_hist, cv2.HISTCMP_CORREL)
                                        
                                        if hist_match > 0.80: # 80% de similaridade nas cores da roupa
                                            name = candidate_name
                                            # "Achei você pela camisa!". Salva esse perfil de rosto doido na memória.
                                            self.known_encodings.append(encoding)
                                            self.known_names.append(name)
                                            self.person_encodings[name].append(encoding)
                                            self.known_histograms[name] = current_hist
                            
                            if name == "Desconhecido":
                                unique_names = list(set(self.known_names))
                                name = f"Pessoa_{len(unique_names) + 1}"
                                self.known_encodings.append(encoding)
                                self.known_names.append(name)
                                self.person_encodings[name].append(encoding)
                                if current_hist is not None:
                                    self.known_histograms[name] = current_hist
                                
                                face_crop = frame[top:bottom, left:right]
                                if face_crop.size > 0:
                                    face_crop_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                                    self.person_faces_rgb[name] = face_crop_rgb
                                    if new_person_callback:
                                        new_person_callback(name, face_crop_rgb)
                                
                            self.tracking_data[name].append((frame_idx, center_x, center_y, box_size))
                            current_frame_faces.append({'name': name, 'box': current_box})
                            
                        last_frame_faces = current_frame_faces
                            
                        if frame_callback and preview_frame is not None:
                            frame_callback(cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB))
                
                frame_idx += 1
                if progress_callback and frame_idx % 30 == 0:
                    progress_callback(frame_idx, self.total_frames)
                    
        cap.release()
        
        # PÓS-PROCESSAMENTO: Fusão Global
        self._merge_identities()
        
        return self._generate_scenes(), self.person_faces_rgb
        
    def _merge_identities(self):
        """
        Análise global post-mortem. Fusão por Exclusão Temporal.
        """
        all_names = list(self.tracking_data.keys())
        if len(all_names) <= 1:
            return
            
        # Para cada pessoa, listar os frames exatos em que apareceu
        person_frames = {}
        for name in all_names:
            person_frames[name] = set([item[0] for item in self.tracking_data[name]])
            
        merged = set()
        merges = [] # (to_keep, to_merge)
        
        for i in range(len(all_names)):
            name_a = all_names[i]
            if name_a in merged:
                continue
                
            for j in range(i + 1, len(all_names)):
                name_b = all_names[j]
                if name_b in merged:
                    continue
                    
                # Checagem de Exclusão Temporal
                # Se a interseção for vazia, eles NUNCA apareceram juntos.
                if not person_frames[name_a].intersection(person_frames[name_b]):
                    # Nunca juntos. Vamos comparar a biometria dos dois globalmente.
                    encodings_a = self.person_encodings.get(name_a, [])
                    encodings_b = self.person_encodings.get(name_b, [])
                    
                    if not encodings_a or not encodings_b:
                        continue
                        
                    # Checar distância mínima entre todos os perfis das duas pessoas
                    min_distance = 1.0
                    for ea in encodings_a:
                        dists = face_recognition.face_distance(encodings_b, ea)
                        if len(dists) > 0:
                            min_dist = np.min(dists)
                            if min_dist < min_distance:
                                min_distance = min_dist
                                
                    # Régua extrema (0.75) porque sabemos que eles nunca estiveram juntos!
                    if min_distance < 0.75:
                        merges.append((name_a, name_b))
                        merged.add(name_b)
                        person_frames[name_a].update(person_frames[name_b])
                        
        # Efetivar a fusão silenciosa (O Cortador nunca saberá que Pessoa B existiu)
        for to_keep, to_merge in merges:
            self.tracking_data[to_keep].extend(self.tracking_data[to_merge])
            del self.tracking_data[to_merge]
        
    def _generate_scenes(self):
        """
        Converte os dados de rastreamento em "Cenas" contínuas para cada pessoa.
        """
        scenes = defaultdict(list)
        
        # Agrupar frames próximos em cenas
        max_gap = self.fps * 2  # Se a pessoa sumir por 2 segundos, não quebra a cena, assume que ainda está lá.
        
        for person, data in self.tracking_data.items():
            if not data:
                continue
                
            # Ordenar por frame
            data.sort(key=lambda x: x[0])
            
            current_scene = {
                'start_frame': data[0][0],
                'end_frame': data[0][0],
                'positions': {data[0][0]: (data[0][1], data[0][2], data[0][3])}
            }
            
            for item in data[1:]:
                frame_idx, cx, cy, size = item
                if frame_idx - current_scene['end_frame'] <= max_gap:
                    current_scene['end_frame'] = frame_idx
                    current_scene['positions'][frame_idx] = (cx, cy, size)
                else:
                    # Salva a cena atual e começa uma nova
                    # Ignorar cenas muito curtas (menos de 2 segundos)
                    if (current_scene['end_frame'] - current_scene['start_frame']) > self.fps * 2:
                        self._smooth_positions(current_scene)
                        scenes[person].append(current_scene)
                    
                    current_scene = {
                        'start_frame': frame_idx,
                        'end_frame': frame_idx,
                        'positions': {frame_idx: (cx, cy, size)}
                    }
                    
            if (current_scene['end_frame'] - current_scene['start_frame']) > self.fps * 2:
                self._smooth_positions(current_scene)
                scenes[person].append(current_scene)
                
        return scenes
        
    def _smooth_positions(self, scene):
        """
        Interpola frames vazios e suaviza a curva de movimento (evitar câmera tremida).
        """
        start = scene['start_frame']
        end = scene['end_frame']
        
        frames = []
        xs = []
        ys = []
        
        # Preencher buracos usando o valor anterior conhecido (interpolação básica)
        last_x, last_y = None, None
        
        for f in range(start, end + 1):
            if f in scene['positions']:
                x, y, _ = scene['positions'][f]
                last_x, last_y = x, y
            else:
                x, y = last_x, last_y
                
            frames.append(f)
            xs.append(x)
            ys.append(y)
            
        # Suavizar movimento
        window = min(int(self.fps) | 1, len(xs) | 1) # Janela ímpar ~1 segundo
        if window > 3 and len(xs) > window:
            xs_smooth = savgol_filter(xs, window, 3)
            ys_smooth = savgol_filter(ys, window, 3)
        else:
            xs_smooth = xs
            ys_smooth = ys
            
        # Atualizar posições com os dados suavizados e preenchidos
        scene['positions_smooth'] = {
            f: (int(xs_smooth[i]), int(ys_smooth[i])) 
            for i, f in enumerate(frames)
        }
