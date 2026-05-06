import os
import numpy as np
from PIL import Image

class AICurator:
    def __init__(self, references_folder="referencias_ideais", log_callback=None):
        self.references_folder = references_folder
        self.log_callback = log_callback or print
        self.reference_embeddings = []
        self.model = None
        self.processor = None
        self.device = "cpu"
        self.is_ready = False
        
        self._initialize()
        
    def _initialize(self):
        if not os.path.exists(self.references_folder):
            os.makedirs(self.references_folder)
            self.log_callback(f"[IA] Pasta '{self.references_folder}' criada. Coloque suas fotos de referência lá.")
            return
            
        valid_exts = (".jpg", ".jpeg", ".png")
        ref_paths = [os.path.join(self.references_folder, f) for f in os.listdir(self.references_folder) if f.lower().endswith(valid_exts)]
        
        if not ref_paths:
            self.log_callback("[IA] Pasta de referências vazia. A IA funcionará no modo padrão sem CLIP.")
            return
            
        self.log_callback("[IA] Carregando modelo CLIP (Isso pode demorar na primeira vez)...")
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel
            
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
            self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            self.log_callback(f"[IA] Calculando Embeddings para {len(ref_paths)} referências...")
            for path in ref_paths:
                try:
                    img = Image.open(path).convert("RGB")
                    inputs = self.processor(images=img, return_tensors="pt").to(self.device)
                    with torch.no_grad():
                        embedding = self.model.get_image_features(**inputs)
                    # Normaliza o vetor para o cálculo de Cosine Similarity
                    embedding = embedding / embedding.norm(dim=-1, keepdim=True)
                    self.reference_embeddings.append(embedding.cpu().numpy())
                except Exception as e:
                    self.log_callback(f"[IA] Erro ao carregar referência {path}: {e}")
                    
            if self.reference_embeddings:
                self.reference_embeddings = np.vstack(self.reference_embeddings)
                self.is_ready = True
                self.log_callback("[IA] Treinamento Semântico concluído. Pronto para curadoria.")
                
        except ImportError:
            self.log_callback("[IA] Bibliotecas 'torch' ou 'transformers' não instaladas. Fallback ativado.")
        except Exception as e:
            self.log_callback(f"[IA] Falha ao inicializar: {e}")
            
    def calculate_similarity(self, frame_rgb):
        """
        Retorna a pontuação máxima de similaridade (Cosine Similarity)
        comparando o frame atual com todas as fotos do portfólio.
        """
        if not self.is_ready:
            return 0.0
            
        try:
            import torch
            img = Image.fromarray(frame_rgb)
            inputs = self.processor(images=img, return_tensors="pt").to(self.device)
            with torch.no_grad():
                frame_embedding = self.model.get_image_features(**inputs)
                
            frame_embedding = frame_embedding / frame_embedding.norm(dim=-1, keepdim=True)
            frame_embedding_np = frame_embedding.cpu().numpy()
            
            # Produto escalar entre a matriz de referências (Nx512) e o frame (1x512)
            similarities = np.dot(self.reference_embeddings, frame_embedding_np.T)
            
            # Extrair o maior valor de similaridade
            best_similarity = np.max(similarities)
            
            # Amplificar a pontuação para equilibrar com pose_score (ex: 80% similaridade = 800 pontos)
            return float(best_similarity * 1000)
            
        except Exception as e:
            # print(f"Erro na inferência: {e}")
            return 0.0
