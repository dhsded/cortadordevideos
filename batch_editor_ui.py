import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
from PIL import Image, ImageEnhance, ImageTk
import threading
import cv2
import numpy as np
import mediapipe as mp
from image_presets import PRESETS, apply_preset

class BatchEditorTab(ctk.CTkFrame):
    def __init__(self, master=None):
        super().__init__(master, fg_color="transparent")
        
        self.image_paths = []
        self.current_preview_path = None
        self.original_preview_img = None
        
        # Variáveis de Ajuste
        self.preset_var = ctk.StringVar(value="00. Original (Sem Filtro)")
        self.upscale_var = ctk.StringVar(value="1x (Original)")
        self.blur_var = ctk.BooleanVar(value=False)
        self.blur_intensity_var = ctk.DoubleVar(value=25.0)
        
        self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
        self.segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=0)
        
        self._build_ui()
        
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- PAINEL LATERAL (Controles) ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#1C1C1C")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        btn_font = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        
        ctk.CTkLabel(self.sidebar, text="Ferramentas em Lote", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(pady=20, padx=10)
        
        self.select_btn = ctk.CTkButton(self.sidebar, text="Selecionar Pasta", command=self.select_folder, fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4, font=btn_font)
        self.select_btn.pack(pady=(0, 20), padx=20, fill="x")
        
        self.info_label = ctk.CTkLabel(self.sidebar, text="Nenhuma foto carregada.", font=ctk.CTkFont(family="Segoe UI", size=11))
        self.info_label.pack(pady=(0, 20), padx=10)
        
        # Filtros removidos do sidebar, agora ficarão na galeria inferior
        
        self.blur_switch = ctk.CTkSwitch(self.sidebar, text="Modo Retrato (Bokeh AI)", variable=self.blur_var, command=self._on_preset_change)
        self.blur_switch.pack(padx=20, pady=(10, 5), fill="x")
        
        self.blur_slider = ctk.CTkSlider(self.sidebar, from_=5, to=55, variable=self.blur_intensity_var, command=self._update_preview_debounce)
        self.blur_slider.pack(padx=20, pady=(0, 20), fill="x")
        
        ctk.CTkLabel(self.sidebar, text="Resolução (Upscale):", anchor="w").pack(padx=20, pady=(10, 0), fill="x")
        self.upscale_menu = ctk.CTkOptionMenu(self.sidebar, variable=self.upscale_var, values=["1x (Original)", "2x (Alta Definição)", "4x (Ultra HD Lanczos)"])
        self.upscale_menu.pack(padx=20, pady=(5, 20), fill="x")
        
        self.apply_btn = ctk.CTkButton(self.sidebar, text="Exportar Todas", command=self.apply_to_all, state="disabled", fg_color="#1F6AA5", hover_color="#144870", corner_radius=4, font=btn_font)
        self.apply_btn.pack(pady=20, padx=20, fill="x", side="bottom")
        
        # --- PAINEL PRINCIPAL (Preview) ---
        self.main_frame = ctk.CTkFrame(self, fg_color="#121212")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(header_frame, text="Visualização (Preview)", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")).pack(side="left")
        
        self.prev_btn = ctk.CTkButton(header_frame, text="< Ant", width=60, command=self.prev_image, state="disabled", fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4)
        self.prev_btn.pack(side="right", padx=(5,0))
        self.next_btn = ctk.CTkButton(header_frame, text="Prox >", width=60, command=self.next_image, state="disabled", fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4)
        self.next_btn.pack(side="right", padx=(5,0))
        
        self.preview_label = ctk.CTkLabel(self.main_frame, text="Preview", bg_color="black", corner_radius=4)
        self.preview_label.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # --- GALERIA DE FILTROS ---
        self.gallery_tabs = ctk.CTkTabview(self.main_frame, height=200, corner_radius=4, fg_color="#1C1C1C")
        self.gallery_tabs.grid(row=2, column=0, sticky="ew")
        
        self.categories = {"Original": [], "PRO Studio": [], "Cinemático": [], "Retrato": [], "P&B": [], "Vintage": [], "Urbano": []}
        for preset_name in PRESETS.keys():
            if "PRO:" in preset_name:
                self.categories["PRO Studio"].append(preset_name)
            elif "Cinem" in preset_name or "Cyber" in preset_name or "Matrix" in preset_name:
                self.categories["Cinemático"].append(preset_name)
            elif "Retrato" in preset_name or "Soft" in preset_name:
                self.categories["Retrato"].append(preset_name)
            elif "P&B" in preset_name or "Noir" in preset_name:
                self.categories["P&B"].append(preset_name)
            elif "Vintage" in preset_name or "Retro" in preset_name or "Film" in preset_name:
                self.categories["Vintage"].append(preset_name)
            elif "Original" in preset_name:
                self.categories["Original"].append(preset_name)
            else:
                self.categories["Urbano"].append(preset_name)
                
        self.gallery_frames = {}
        for cat_name in self.categories.keys():
            self.gallery_tabs.add(cat_name)
            scroll = ctk.CTkScrollableFrame(self.gallery_tabs.tab(cat_name), orientation="horizontal", height=130, fg_color="transparent")
            scroll.pack(fill="both", expand=True)
            self.gallery_frames[cat_name] = scroll
        
    def _on_preset_change(self, _=None):
        self.apply_filters_and_show()
        
    def select_folder(self):
        folder = filedialog.askdirectory(title="Selecione a pasta com as imagens Raw")
        if not folder:
            return
            
        valid_exts = (".jpg", ".jpeg", ".png")
        self.image_paths = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(valid_exts):
                    self.image_paths.append(os.path.join(root, f))
        
        if not self.image_paths:
            messagebox.showinfo("Vazio", "Nenhuma imagem encontrada na pasta.")
            return
            
        self.info_label.configure(text=f"{len(self.image_paths)} fotos carregadas.")
        self.apply_btn.configure(state="normal")
        self.prev_btn.configure(state="normal")
        self.next_btn.configure(state="normal")
        
        self.current_idx = 0
        self.load_preview(self.image_paths[self.current_idx])
        
    def load_preview(self, path):
        self.current_preview_path = path
        img_pil = Image.open(path).convert("RGB")
        self.original_preview_img = img_pil
        
        # Gerar miniaturas da galeria de filtros em Thread para não travar a UI
        threading.Thread(target=self._generate_thumbnails, args=(img_pil.copy(),), daemon=True).start()
        
        self.apply_filters_and_show()
        
    def _generate_thumbnails(self, base_img):
        base_img.thumbnail((150, 150))
        
        def _clear_and_build():
            # Limpar botões antigos
            for scroll in self.gallery_frames.values():
                for widget in scroll.winfo_children():
                    widget.destroy()
            
            # Criar novos
            for cat_name, presets in self.categories.items():
                scroll = self.gallery_frames[cat_name]
                for preset in presets:
                    # Aplicar filtro na miniatura
                    thumb_filtered = apply_preset(base_img.copy(), preset)
                    ctk_thumb = ctk.CTkImage(light_image=thumb_filtered, dark_image=thumb_filtered, size=(100, 100))
                    
                    frame = ctk.CTkFrame(scroll, fg_color="transparent")
                    frame.pack(side="left", padx=5)
                    
                    btn = ctk.CTkButton(frame, image=ctk_thumb, text="", width=100, height=100, corner_radius=8, 
                                        fg_color="transparent", hover_color="#333333",
                                        command=lambda p=preset: self._select_preset_from_gallery(p))
                    btn.pack()
                    btn.image = ctk_thumb # keep ref
                    
                    lbl = ctk.CTkLabel(frame, text=preset[:15] + "..." if len(preset)>15 else preset, font=ctk.CTkFont(size=10))
                    lbl.pack()
                    
        self.after(0, _clear_and_build)
        
    def _select_preset_from_gallery(self, preset_name):
        self.preset_var.set(preset_name)
        self._on_preset_change(None)
        
    def next_image(self):
        if self.image_paths:
            self.current_idx = (self.current_idx + 1) % len(self.image_paths)
            self.load_preview(self.image_paths[self.current_idx])
            
    def prev_image(self):
        if self.image_paths:
            self.current_idx = (self.current_idx - 1) % len(self.image_paths)
            self.load_preview(self.image_paths[self.current_idx])

    def _update_preview_debounce(self, _):
        # Evita travar a UI ao arrastar o slider muito rápido
        if hasattr(self, '_timer'):
            self.after_cancel(self._timer)
        self._timer = self.after(100, self.apply_filters_and_show)
        
    def get_processed_image(self, img_pil, is_export=False):
        # 1. Efeito Bokeh / Desfoque de Fundo
        if self.blur_var.get():
            img_np = np.array(img_pil)
            results = self.segmentation.process(img_np)
            mask = results.segmentation_mask
            
            if mask is not None:
                # Converter máscara para 3 canais e definir threshold suave
                condition = np.stack((mask,) * 3, axis=-1) > 0.5
                
                # Nível de desfoque
                k_size = int(self.blur_intensity_var.get())
                if k_size % 2 == 0:
                    k_size += 1
                    
                blurred_bg = cv2.GaussianBlur(img_np, (k_size, k_size), 0)
                output_image = np.where(condition, img_np, blurred_bg)
                img_pil = Image.fromarray(output_image)
                
        # 2. Presets de Cores
        img_pil = apply_preset(img_pil, self.preset_var.get())
        
        if is_export:
            scale_str = self.upscale_var.get()
            if "2x" in scale_str:
                img_pil = img_pil.resize((img_pil.width * 2, img_pil.height * 2), Image.LANCZOS)
            elif "4x" in scale_str:
                img_pil = img_pil.resize((img_pil.width * 4, img_pil.height * 4), Image.LANCZOS)
                
        return img_pil
        
    def apply_filters_and_show(self):
        if not self.original_preview_img:
            return
            
        processed = self.get_processed_image(self.original_preview_img.copy(), is_export=False)
        
        # Redimensionar para caber no preview da UI sem upscale
        target_w = self.preview_label.winfo_width()
        target_h = self.preview_label.winfo_height()
        if target_w <= 10 or target_h <= 10:
            target_w, target_h = 400, 600
            
        ratio = min(target_w / processed.width, target_h / processed.height)
        new_w = int(processed.width * ratio)
        new_h = int(processed.height * ratio)
        
        display_img = processed.resize((new_w, new_h), Image.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=display_img, dark_image=display_img, size=(new_w, new_h))
        
        self.preview_label.configure(image=ctk_img, text="")
        
    def apply_to_all(self):
        if not self.image_paths:
            return
            
        self.apply_btn.configure(state="disabled", text="Processando...")
        
        def worker():
            try:
                first_img_dir = os.path.dirname(self.image_paths[0])
                output_dir = os.path.join(first_img_dir, "editadas")
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    
                total = len(self.image_paths)
                for idx, path in enumerate(self.image_paths):
                    img = Image.open(path).convert("RGB")
                    final_img = self.get_processed_image(img, is_export=True)
                    
                    filename = os.path.basename(path)
                    # Forçar qualidade máxima para JPEGs
                    save_path = os.path.join(output_dir, filename)
                    final_img.save(save_path, quality=100, subsampling=0)
                    
                self.after(0, messagebox.showinfo, "Sucesso", f"{total} fotos exportadas com sucesso em máxima qualidade para:\n{output_dir}")
            except Exception as e:
                self.after(0, messagebox.showerror, "Erro", f"Erro ao processar lote: {e}")
            finally:
                self.after(0, self.apply_btn.configure, {"state": "normal", "text": "Exportar Todas"})
                
        threading.Thread(target=worker, daemon=True).start()
