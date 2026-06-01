import cv2
import face_recognition
import numpy as np
import os
import threading
from queue import Queue
from collections import defaultdict
from scipy.signal import savgol_filter

class FileVideoStream:
    def __init__(self, path, queue_size=256):
        self.stream = cv2.VideoCapture(path)
        self.stopped = False
        self.Q = Queue(maxsize=queue_size)

        # Detectar rotação do vídeo (vídeos gravados em portrait no celular)
        # 99 = cv2.CAP_PROP_ORIENTATION_META (OpenCV 4.5.4+)
        self._rotate_code = None
        try:
            rot = int(self.stream.get(99))
            if rot == 90:
                self._rotate_code = cv2.ROTATE_90_CLOCKWISE
            elif rot == 180:
                self._rotate_code = cv2.ROTATE_180
            elif rot in [270, -90]:
                self._rotate_code = cv2.ROTATE_90_COUNTERCLOCKWISE
        except Exception:
            pass
        
    def start(self):
        t = threading.Thread(target=self.update, args=())
        t.daemon = True
        t.start()
        return self
        
    def update(self):
        while True:
            if self.stopped:
                return
            if not self.Q.full():
                try:
                    ret, frame = self.stream.read()
                    if not ret:
                        self.stop()
                        return
                    # Corrigir orientação se o vídeo estiver rotacionado
                    if self._rotate_code is not None:
                        frame = cv2.rotate(frame, self._rotate_code)
                    self.Q.put(frame)
                except Exception:
                    import time
                    time.sleep(0.01)
                    continue
            else:
                import time
                time.sleep(0.01)
                
    def read(self):
        return self.Q.get()
        
    def more(self):
        return self.Q.qsize() > 0 or not self.stopped
        
    def stop(self):
        self.stopped = True
        self.stream.release()

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
        self.width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # Se o vídeo estiver rotacionado 90°/270°, largura e altura ficam trocadas
        try:
            rot = int(self.cap.get(99))  # CAP_PROP_ORIENTATION_META
            if rot in [90, 270]:
                self.width, self.height = self.height, self.width
        except Exception:
            pass
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

    def process_video(self, preview_mode="Total", progress_callback=None, frame_callback=None, new_person_callback=None, cancel_event=None, log_callback=None):
        import mediapipe as mp
        # Importação explícita para o PyInstaller não se perder
        import mediapipe.python.solutions.face_detection as mp_face_detection_module
        mp_face_detection = mp.solutions.face_detection if hasattr(mp, 'solutions') else mp_face_detection_module
        
        def _log(msg):
            if log_callback:
                log_callback(msg)
        
        fvs = FileVideoStream(self.video_path, queue_size=256).start()
        frame_idx = 0
        last_log_pct = -1
        last_detection_frame_idx = -1  # Frame em que rostos foram detectados pela última vez
        
        last_frame_faces = [] # list of {'name': name, 'box': box}
        
        # Sensibilidade aumentada: min_detection_confidence = 0.35 para capturar rostos de perfil, em sombra ou sob ângulos difíceis
        with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.35) as face_detection:
            while fvs.more():
                if cancel_event and cancel_event.is_set():
                    break
                    
                try:
                    frame = fvs.read()
                except:
                    break
                    
                if frame is None:
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
                            # Filtro de Protagonistas: Ignorar rostos menores que 8% do maior rosto do frame
                            # (valor baixo para capturar pessoas ao fundo, em grupo ou de passagem)
                            max_box_size = max([max(r - l, b - t) for (t, r, b, l) in face_locations])
                            primary_face_locations = []
                            for loc in face_locations:
                                t, r, b, l = loc
                                box_size = max(r - l, b - t)
                                if box_size >= max_box_size * 0.08:
                                    primary_face_locations.append(loc)
                            face_locations = primary_face_locations
                    
                    if not face_locations:
                        last_frame_faces = [] # Perdeu todo mundo
                        if frame_callback and preview_mode != "Desligado":
                            if preview_mode == "Total" or (preview_mode == "Metade" and frame_idx % (self.sample_rate * 2) == 0) or (preview_mode == "1/4" and frame_idx % (self.sample_rate * 4) == 0):
                                frame_callback(rgb_frame)
                    else:
                        # Biometria de Alta Definição: num_jitters=2 para melhor qualidade de encoding
                        # especialmente em rostos de perfil, sob ângulos difíceis ou com oclusão parcial.
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
                            # Só é válido se a detecção anterior foi RECENTE.
                            # Sem isso, pessoa B que entra onde pessoa A saiu herda a identidade de A via sobreposição de caixas.
                            iou_max_gap = self.sample_rate * 3  # Tolerância: até 3 frames analisados atrás
                            iou_is_valid = (last_detection_frame_idx >= 0 and
                                            (frame_idx - last_detection_frame_idx) <= iou_max_gap)
                            
                            best_iou = 0
                            best_iou_name = None
                            if iou_is_valid:
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
                        last_detection_frame_idx = frame_idx  # Atualiza o timestamp da última detecção válida
                            
                        if frame_callback and preview_frame is not None and preview_mode != "Desligado":
                            if preview_mode == "Total" or (preview_mode == "Metade" and frame_idx % (self.sample_rate * 2) == 0) or (preview_mode == "1/4" and frame_idx % (self.sample_rate * 4) == 0):
                                frame_callback(cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB))
                
                frame_idx += 1
                if progress_callback and frame_idx % 30 == 0:
                    progress_callback(frame_idx, self.total_frames)
                # Log de progresso a cada 5% dos frames
                if self.total_frames > 0:
                    pct = int((frame_idx / self.total_frames) * 100)
                    pct_bucket = pct // 5
                    if pct_bucket != last_log_pct:
                        last_log_pct = pct_bucket
                        pessoas = len(set(self.known_names))
                        _log(f"Fase 1: {pct}% analisado ({frame_idx}/{self.total_frames} frames) | {pessoas} pessoa(s) encontrada(s) ate agora")
                    
        fvs.stop()

        # Garantir que a barra chegue a 100% ao finalizar
        if progress_callback:
            progress_callback(self.total_frames, self.total_frames)

        # POS-PROCESSAMENTO: Fusao Global
        _log("Fase 1: Rastreamento concluido! Iniciando fusao de identidades (pode demorar)...")
        self._merge_identities(log_callback=log_callback)
        _log(f"Fase 1: Fusao concluida! {len(self.tracking_data)} identidade(s) final(is).")
        
        return self._generate_scenes(), self.person_faces_rgb
        
    def _merge_identities(self, log_callback=None):
        """
        Análise global post-mortem. Fusão por Exclusão Temporal.
        """
        def _log(msg):
            if log_callback:
                log_callback(msg)
                
        all_names = list(self.tracking_data.keys())
        _log(f"Fusao: Comparando {len(all_names)} identidade(s) detectadas...")
        if len(all_names) <= 1:
            return
            
        # Para cada pessoa, listar os frames exatos em que apareceu
        person_frames = {}
        for name in all_names:
            person_frames[name] = set([item[0] for item in self.tracking_data[name]])
            
        merged = set()
        merges = []

        for i in range(len(all_names)):
            name_a = all_names[i]
            if name_a in merged:
                continue

            if i % 3 == 0:
                _log(f"Fusao: analisando identidade {i+1}/{len(all_names)}...")

            for j in range(i + 1, len(all_names)):
                name_b = all_names[j]
                if name_b in merged:
                    continue

                if not person_frames[name_a].intersection(person_frames[name_b]):
                    encodings_a = self.person_encodings.get(name_a, [])
                    encodings_b = self.person_encodings.get(name_b, [])

                    if not encodings_a or not encodings_b:
                        continue

                    # Limitar a 50 encodings por pessoa para evitar lentidão
                    sample_a = encodings_a[-50:]
                    sample_b = encodings_b[-50:]

                    min_distance = 1.0
                    for ea in sample_a:
                        dists = face_recognition.face_distance(sample_b, ea)
                        if len(dists) > 0:
                            d = np.min(dists)
                            if d < min_distance:
                                min_distance = d

                    if min_distance < 0.75:
                        merges.append((name_a, name_b))
                        merged.add(name_b)
                        person_frames[name_a].update(person_frames[name_b])

        for to_keep, to_merge in merges:
            self.tracking_data[to_keep].extend(self.tracking_data[to_merge])
            del self.tracking_data[to_merge]
        if merges:
            _log(f"Fusao: {len(merges)} identidade(s) fundida(s). Total final: {len(self.tracking_data)} pessoa(s).")
        else:
            _log(f"Fusao: Nenhuma identidade fundida. Total: {len(self.tracking_data)} pessoa(s).")
        
    def _generate_scenes(self):
        """
        Converte os dados de rastreamento em "Cenas" contínuas para cada pessoa.
        """
        scenes = defaultdict(list)
        
        # Encerrar cena se pessoa sumir por mais de 0.5s.
        max_gap = int(self.fps * 0.5)
        # Minimo de 5 frames (~0.17s a 30fps) para evitar deteccoes de 1-2 frames.
        # O video_cutter e responsavel por filtrar/slow-motion cenas curtas.
        min_scene_frames = max(5, self.fps * 0.17)
        
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
                    # Salva a cena atual e começa uma nova.
                    # Mínimo de 1.5s: filtra detecções espúrias que não geram vídeos úteis.
                    if (current_scene['end_frame'] - current_scene['start_frame']) > min_scene_frames:
                        self._smooth_positions(current_scene)
                        scenes[person].append(current_scene)
                    
                    current_scene = {
                        'start_frame': frame_idx,
                        'end_frame': frame_idx,
                        'positions': {frame_idx: (cx, cy, size)}
                    }
                    
            if (current_scene['end_frame'] - current_scene['start_frame']) > min_scene_frames:
                self._smooth_positions(current_scene)
                scenes[person].append(current_scene)
                
        return scenes
        
    def _smooth_positions(self, scene):
        """
        Interpola frames vazios e suaviza a curva de movimento (evitar câmera tremida).
        
        Usa interpolação linear bidirecional (np.interp) em vez de forward-fill.
        Isso garante que frames sem detecção recebem uma posição calculada como média
        entre o último ponto conhecido ANTES e o próximo ponto conhecido DEPOIS —
        evitando saltos abruptos para posições de outros momentos do vídeo.
        """
        start = scene['start_frame']
        end = scene['end_frame']
        
        all_frames = list(range(start, end + 1))
        
        # Separar frames onde realmente detectamos a pessoa dos frames vazios
        known_frames = sorted(scene['positions'].keys())
        known_xs = [scene['positions'][f][0] for f in known_frames]
        known_ys = [scene['positions'][f][1] for f in known_frames]
        
        if not known_frames:
            scene['positions_smooth'] = {}
            return
        
        if len(known_frames) == 1:
            # Apenas um ponto conhecido: preencher tudo com ele
            cx, cy = known_xs[0], known_ys[0]
            scene['positions_smooth'] = {f: (cx, cy) for f in all_frames}
            return
        
        # Interpolação linear verdadeira (bidirecional) para todos os frames da cena.
        # np.interp usa os pontos conhecidos como âncoras e interpola linearmente entre eles.
        # Para frames fora do range dos conhecidos, usa o valor do extremo mais próximo (clamp).
        xs_interp = np.interp(all_frames, known_frames, known_xs)
        ys_interp = np.interp(all_frames, known_frames, known_ys)
        
        # Suavizar movimento com Savitzky-Golay para evitar câmera tremida
        window = min(int(self.fps) | 1, len(xs_interp) | 1)  # Janela ímpar ~1 segundo
        if window > 3 and len(xs_interp) > window:
            xs_smooth = savgol_filter(xs_interp, window, 3)
            ys_smooth = savgol_filter(ys_interp, window, 3)
        else:
            xs_smooth = xs_interp
            ys_smooth = ys_interp
            
        # Atualizar posições com os dados suavizados e preenchidos
        scene['positions_smooth'] = {
            f: (int(xs_smooth[i]), int(ys_smooth[i])) 
            for i, f in enumerate(all_frames)
        }
