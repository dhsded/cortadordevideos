import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import cv2
from PIL import Image
import logging

from video_tracker import VideoTracker
from video_cutter import VideoCutter
from flow_editor_ui import FlowEditorUI

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Cortador Inteligente 9:16 - Edição Profissional")
        self.geometry("1100x700")
        
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except:
            pass
        
        self.video_path = None
        self.output_dir = None
        self.cancel_event = threading.Event()
        
        self.quality_bitrate_map = {
            "Baixa": "1000k",
            "Média": "2500k",
            "Boa": "5000k",
            "Alta": "8000k",
            "Superior": "12000k"
        }
        
        # --- Layout Principal ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Sidebar (Esquerda) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Auto-Cutter Pro", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.select_btn = ctk.CTkButton(self.sidebar_frame, text="1. Selecionar Vídeo", command=self.select_video)
        self.select_btn.grid(row=1, column=0, padx=20, pady=10)
        self.file_label = ctk.CTkLabel(self.sidebar_frame, text="Nenhum vídeo selecionado", font=ctk.CTkFont(size=10), text_color="gray", wraplength=200)
        self.file_label.grid(row=2, column=0, padx=20, pady=(0, 10))
        
        self.output_btn = ctk.CTkButton(self.sidebar_frame, text="2. Pasta de Saída", command=self.select_output_dir)
        self.output_btn.grid(row=3, column=0, padx=20, pady=10)
        self.output_label = ctk.CTkLabel(self.sidebar_frame, text="Pasta: Padrão ('output_cortes')", font=ctk.CTkFont(size=10), text_color="gray", wraplength=200)
        self.output_label.grid(row=4, column=0, padx=20, pady=(0, 10))
        
        self.flow_btn = ctk.CTkButton(self.sidebar_frame, text="📸 Editor Flow IA", fg_color="#E67E22", hover_color="#D35400", command=self.open_flow_editor)
        self.flow_btn.grid(row=4, column=0, padx=20, pady=(40, 10), sticky="s")
        
        self.quality_label = ctk.CTkLabel(self.sidebar_frame, text="Qualidade de Exportação:")
        self.quality_label.grid(row=5, column=0, padx=20, pady=(10, 0), sticky="s")
        self.quality_var = ctk.StringVar(value="Boa")
        self.quality_menu = ctk.CTkOptionMenu(self.sidebar_frame, variable=self.quality_var, values=list(self.quality_bitrate_map.keys()))
        self.quality_menu.grid(row=6, column=0, padx=20, pady=10, sticky="s")
        
        self.start_btn = ctk.CTkButton(self.sidebar_frame, text="Iniciar Processamento", command=self.start_processing, state="disabled", fg_color="green", hover_color="darkgreen")
        self.start_btn.grid(row=7, column=0, padx=20, pady=10, sticky="s")
        
        self.cancel_btn = ctk.CTkButton(self.sidebar_frame, text="Cancelar", command=self.cancel_processing, state="disabled", fg_color="red", hover_color="darkred")
        self.cancel_btn.grid(row=8, column=0, padx=20, pady=(0, 20), sticky="s")
        
        # --- Área Principal (Centro/Direita) ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_rowconfigure(1, weight=1) # preview
        self.main_frame.grid_rowconfigure(6, weight=1) # log
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Preview
        self.preview_title = ctk.CTkLabel(self.main_frame, text="Visualização ao Vivo", font=ctk.CTkFont(size=14, weight="bold"))
        self.preview_title.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.preview_label = ctk.CTkLabel(self.main_frame, text="Aguardando...", bg_color="black", corner_radius=10)
        self.preview_label.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        # Galeria de Rostos
        self.gallery_title = ctk.CTkLabel(self.main_frame, text="Rostos Detectados (0)", font=ctk.CTkFont(size=14, weight="bold"))
        self.gallery_title.grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        self.gallery_frame = ctk.CTkScrollableFrame(self.main_frame, orientation="horizontal", height=100)
        self.gallery_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        # Status e Progresso
        self.status_label = ctk.CTkLabel(self.main_frame, text="Pronto para iniciar.", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=4, column=0, sticky="w", pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self.progress_bar.set(0)
        
        # Log
        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=100, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.grid(row=6, column=0, sticky="nsew")
        self.log_textbox.insert("0.0", "--- Log do Sistema ---\n")
        self.log_textbox.configure(state="disabled")

    def log(self, message):
        self.after(0, self._log, message)
        
    def _log(self, message):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def select_output_dir(self):
        directory = filedialog.askdirectory(title="Selecione a pasta de saída")
        if directory:
            self.output_dir = directory
            self.output_label.configure(text=f"Pasta: {os.path.basename(directory)}")
            self.log(f"Pasta de saída definida: {directory}")

    def open_flow_editor(self):
        # Evitar múltiplas janelas abertas
        if not hasattr(self, 'flow_window') or not self.flow_window.winfo_exists():
            self.flow_window = FlowEditorUI(self)
        else:
            self.flow_window.focus()

    def select_video(self):
        filename = filedialog.askopenfilename(
            title="Selecione um vídeo",
            filetypes=[("Arquivos de Vídeo", "*.mp4 *.avi *.mov *.mkv")]
        )
        if filename:
            self.video_path = filename
            self.file_label.configure(text=os.path.basename(filename))
            self.start_btn.configure(state="normal")
            self.log(f"Vídeo selecionado: {filename}")
            
    def update_progress(self, current, total, text_prefix):
        percentage = current / total if total > 0 else 0
        self.after(0, self.progress_bar.set, percentage)
        self.after(0, self.status_label.configure, {"text": f"{text_prefix} {current}/{total} ({int(percentage*100)}%)"})
        
    def update_preview(self, frame_rgb):
        try:
            img = Image.fromarray(frame_rgb)
            img.thumbnail((640, 360)) # Ajustar ao painel
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            
            def set_image():
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img # Mantém a referência para não sumir da tela
                
            self.after(0, set_image)
        except Exception:
            pass

    def add_face_gallery(self, name, face_rgb):
        try:
            img = Image.fromarray(face_rgb)
            img.thumbnail((80, 80))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            
            def _add():
                frame = ctk.CTkFrame(self.gallery_frame, fg_color="transparent")
                frame.pack(side="left", padx=5)
                lbl_img = ctk.CTkLabel(frame, image=ctk_img, text="")
                lbl_img.pack()
                lbl_txt = ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(size=10))
                lbl_txt.pack()
                
                count = len(self.gallery_frame.winfo_children())
                self.gallery_title.configure(text=f"Rostos Detectados ({count})")
            
            self.after(0, _add)
        except Exception as e:
            self.log(f"Erro ao adicionar rosto na galeria: {e}")

    def cancel_processing(self):
        self.log("Sinal de cancelamento enviado. Aguarde a interrupção...")
        self.cancel_event.set()
        self.cancel_btn.configure(state="disabled")

    def processing_thread(self):
        try:
            self.cancel_event.clear()
            self.log("Iniciando Fase 1: Rastreamento de rostos...")
            self.after(0, self.status_label.configure, {"text": "Fase 1: Analisando rostos e movimentos..."})
            self.after(0, self.progress_bar.set, 0)
            
            # Limpar galeria
            for widget in self.gallery_frame.winfo_children():
                widget.destroy()
            self.after(0, self.gallery_title.configure, {"text": "Rostos Detectados (0)"})
            
            tracker = VideoTracker(self.video_path, sample_rate=15)
            
            def track_progress(current, total):
                self.update_progress(current, total, "Fase 1: Analisando frame")
                
            def new_person_cb(name, face_rgb):
                self.log(f"Nova pessoa detectada: {name}")
                self.add_face_gallery(name, face_rgb)
                
            scenes, final_faces_rgb = tracker.process_video(
                progress_callback=track_progress, 
                frame_callback=self.update_preview,
                new_person_callback=new_person_cb,
                cancel_event=self.cancel_event
            )
            
            if self.cancel_event.is_set():
                self.log("Processamento cancelado pelo usuário durante o rastreamento.")
                self.after(0, messagebox.showwarning, "Cancelado", "O processamento foi interrompido.")
                return

            if not scenes:
                self.log("Nenhuma pessoa encontrada no vídeo.")
                self.after(0, messagebox.showinfo, "Aviso", "Nenhuma pessoa detectada no vídeo.")
                return
                
            # Limpar galeria antiga (que pode ter duplicados antes da Fusão Temporal)
            for widget in self.gallery_frame.winfo_children():
                widget.destroy()
            
            # Redesenhar apenas as identidades que sobreviveram à Fusão
            self.after(0, self.gallery_title.configure, {"text": f"Rostos Detectados ({len(scenes)})"})
            for final_name in scenes.keys():
                if final_name in final_faces_rgb:
                    self.add_face_gallery(final_name, final_faces_rgb[final_name])
                
            total_scenes = sum(len(s) for s in scenes.values())
            self.log(f"Fase 1 concluída! {len(scenes)} pessoa(s) e {total_scenes} cena(s) identificadas.")
            self.log("Iniciando Fase 2: Recorte e Renderização...")
            self.after(0, self.status_label.configure, {"text": "Fase 2: Aplicando Auto-Reframe (9:16) e renderizando..."})
            self.after(0, self.progress_bar.set, 0)
            
            final_output_dir = self.output_dir if self.output_dir else os.path.join(os.path.dirname(self.video_path), "output_cortes")
            cutter = VideoCutter(self.video_path, output_dir=final_output_dir)
            
            def cut_progress(current, total):
                if total == 100:
                    self.update_progress(current, total, "Fase 2: Renderizando vídeo")
                else:
                    self.update_progress(current, total, "Fase 2: Concluindo pessoa")
                    self.log(f"Processamento de vídeo de pessoa concluído ({current}/{total}).")
                
            selected_quality = self.quality_var.get()
            bitrate = self.quality_bitrate_map.get(selected_quality, "5000k")
            
            self.log(f"Qualidade de renderização: {selected_quality} ({bitrate})")
            
            cutter.cut_scenes(
                scenes, 
                tracker.fps, 
                bitrate=bitrate, 
                progress_callback=cut_progress, 
                frame_callback=self.update_preview,
                cancel_event=self.cancel_event
            )
            
            if self.cancel_event.is_set():
                self.log("Processamento cancelado pelo usuário durante a renderização.")
                self.after(0, messagebox.showwarning, "Cancelado", "A renderização foi interrompida. Alguns arquivos podem estar incompletos.")
                return

            self.log("Processamento concluído com sucesso!")
            self.after(0, self.status_label.configure, {"text": "Processamento Concluído com Sucesso!"})
            self.after(0, self.progress_bar.set, 1)
            self.after(0, messagebox.showinfo, "Sucesso", f"Vídeos exportados na pasta:\n{final_output_dir}")
            
        except Exception as e:
            self.log(f"Erro grave: {str(e)}")
            self.after(0, messagebox.showerror, "Erro", f"Ocorreu um erro: {str(e)}")
        finally:
            self.after(0, self._reset_ui)
            
    def _reset_ui(self):
        self.start_btn.configure(state="normal")
        self.select_btn.configure(state="normal")
        self.output_btn.configure(state="normal")
        self.quality_menu.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text="Pronto para novo processamento.")
        self.progress_bar.set(0)
        
    def start_processing(self):
        self.start_btn.configure(state="disabled")
        self.select_btn.configure(state="disabled")
        self.output_btn.configure(state="disabled")
        self.quality_menu.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        
        self.log("--- Novo Processamento ---")
        thread = threading.Thread(target=self.processing_thread, daemon=True)
        thread.start()

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
