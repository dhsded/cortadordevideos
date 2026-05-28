import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import cv2
from PIL import Image
import logging
import time
import winsound
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from batch_editor_ui import BatchEditorTab
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
            
        import subprocess
        
        self.mode_var = ctk.StringVar(value="Ambos")
        self.duration_var = ctk.StringVar(value="50")
        self.min_dur_var = ctk.StringVar(value="8")  # Duração mínima do vídeo (câmera lenta)
        self.photos_var = ctk.StringVar(value="5")
        self.quality_var = ctk.StringVar(value="Boa")
        self.hw_var = ctk.StringVar(value="CPU")
        self.sound_var = ctk.StringVar(value="Soft Bell")
        
        self._auto_detect_hardware()
        
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
        self.configure(fg_color="#121212")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Sidebar (Esquerda) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#1C1C1C")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Auto-Cutter Pro", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        btn_font = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        
        self.select_btn = ctk.CTkButton(self.sidebar_frame, text="1. Selecionar Vídeo", command=self.select_video, fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4, font=btn_font)
        self.select_btn.grid(row=1, column=0, padx=20, pady=5)
        self.file_label = ctk.CTkLabel(self.sidebar_frame, text="Nenhum vídeo selecionado", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="gray", wraplength=200)
        self.file_label.grid(row=2, column=0, padx=20, pady=(0, 5))
        
        self.output_btn = ctk.CTkButton(self.sidebar_frame, text="2. Pasta de Saída", command=self.select_output_dir, fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4, font=btn_font)
        self.output_btn.grid(row=3, column=0, padx=20, pady=5)
        self.output_label = ctk.CTkLabel(self.sidebar_frame, text="Pasta: Padrão ('output_cortes')", font=ctk.CTkFont(size=10), text_color="gray", wraplength=200)
        self.output_label.grid(row=4, column=0, padx=20, pady=(0, 5))
        
        # Botão de Configurações
        self.settings_btn = ctk.CTkButton(self.sidebar_frame, text="⚙️ Configurações Gerais", command=self.open_settings_window, fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4, font=btn_font)
        self.settings_btn.grid(row=6, column=0, padx=20, pady=(15, 5))

        self.flow_btn = ctk.CTkButton(self.sidebar_frame, text="📸 Editor Flow IA", fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4, command=self.open_flow_editor)
        self.flow_btn.grid(row=7, column=0, padx=20, pady=(10, 10), sticky="s")
        

        self.start_btn = ctk.CTkButton(self.sidebar_frame, text="Iniciar Processamento", command=self.start_processing, state="disabled", fg_color="#1F6AA5", hover_color="#144870", corner_radius=4, font=btn_font)
        self.start_btn.grid(row=9, column=0, padx=20, pady=(5, 5), sticky="s")
        
        self.cancel_btn = ctk.CTkButton(self.sidebar_frame, text="Cancelar", command=self.cancel_processing, state="disabled", fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4)
        self.cancel_btn.grid(row=10, column=0, padx=20, pady=(0, 15), sticky="s")
        
        # --- Área Principal (Centro/Direita) ---
        self.tabview = ctk.CTkTabview(self, corner_radius=4, fg_color="#181818")
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.tabview.add("Processamento")
        self.tabview.add("Editor em Lote")
        self.tabview.add("Relatório de Desempenho")
        
        self.main_frame = self.tabview.tab("Processamento")
        self.main_frame.grid_rowconfigure(1, weight=1) # preview
        self.main_frame.grid_rowconfigure(6, weight=1) # log
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        self.perf_frame = self.tabview.tab("Relatório de Desempenho")
        self.perf_frame.grid_rowconfigure(0, weight=1)
        self.perf_frame.grid_columnconfigure(0, weight=1)
        
        self.perf_canvas_frame = ctk.CTkFrame(self.perf_frame, fg_color="transparent")
        self.perf_canvas_frame.grid(row=0, column=0, sticky="nsew")
        
        self.batch_frame = self.tabview.tab("Editor em Lote")
        self.batch_frame.grid_rowconfigure(0, weight=1)
        self.batch_frame.grid_columnconfigure(0, weight=1)
        self.batch_tab_ui = BatchEditorTab(self.batch_frame)
        self.batch_tab_ui.pack(fill="both", expand=True)
        
        # Preview Header
        self.preview_header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.preview_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        self.preview_title = ctk.CTkLabel(self.preview_header_frame, text="Visualização ao Vivo", font=ctk.CTkFont(size=14, weight="bold"))
        self.preview_title.pack(side="left")
        
        self.preview_var = ctk.StringVar(value="Metade")
        self.preview_menu = ctk.CTkOptionMenu(self.preview_header_frame, variable=self.preview_var, values=["Total", "Metade", "1/4", "Desligado"], width=100)
        self.preview_menu.pack(side="right")
        
        ctk.CTkLabel(self.preview_header_frame, text="Escala do Preview:").pack(side="right", padx=10)
        
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
        
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_bar.set(0)
        
        self.percent_label = ctk.CTkLabel(self.progress_frame, text="0%", font=ctk.CTkFont(size=12, weight="bold"))
        self.percent_label.pack(side="right", padx=(10, 0))
        
        # Log
        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=100, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.grid(row=6, column=0, sticky="nsew")
        self.log_textbox.insert("0.0", "--- Log do Sistema ---\n")
        self.log_textbox.configure(state="disabled")

    def log(self, message):
        self.after(0, self._log, message)
        
    def _log(self, message):
        prefix = ""
        if hasattr(self, 'process_start_time') and self.process_start_time is not None:
            elapsed = int(time.time() - self.process_start_time)
            m = elapsed // 60
            s = elapsed % 60
            prefix = f"[{m:02d}:{s:02d}] "
            
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", prefix + message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def select_output_dir(self):
        directory = filedialog.askdirectory(title="Selecione a pasta de saída")
        if directory:
            self.output_dir = directory
            self.output_label.configure(text=f"Pasta: {os.path.basename(directory)}")
            self.log(f"Pasta de saída definida: {directory}")

    def open_flow_editor(self):
        editor = FlowEditorUI(self)
        editor.grab_set()

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
        self.after(0, self.percent_label.configure, {"text": f"{int(percentage*100)}%"})
        self.after(0, self.status_label.configure, {"text": f"{text_prefix} {current}/{total}"})
        
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
            self.process_start_time = time.time()
            t_total_start = self.process_start_time
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
                
            t_start_phase1 = time.time()
            scenes, final_faces_rgb = tracker.process_video(
                preview_mode=self.preview_var.get(),
                progress_callback=track_progress, 
                frame_callback=self.update_preview,
                new_person_callback=new_person_cb,
                cancel_event=self.cancel_event,
                log_callback=self.log
            )
            time_phase1 = time.time() - t_start_phase1
            
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
            self.log(f"Fase 1 concluída em {time_phase1:.1f}s! {len(scenes)} pessoa(s) detectada(s).")
            self.log(f"Total de cenas identificadas: {total_scenes}")
            for pname, pscenes in scenes.items():
                dur_total = sum((s['end_frame'] - s['start_frame']) / tracker.fps for s in pscenes)
                self.log(f"  -> {pname}: {len(pscenes)} cena(s), ~{dur_total:.1f}s de presença no vídeo")
            self.log("Iniciando Fase 2: Recorte e Renderização...")
            self.after(0, self.status_label.configure, {"text": "Fase 2: Aplicando Auto-Reframe (9:16) e renderizando..."})
            self.after(0, self.progress_bar.set, 0)
            
            final_output_dir = self.output_dir if self.output_dir else os.path.join(os.path.dirname(self.video_path), "output_cortes")
            self.log(f"Pasta de saída: {final_output_dir}")
            cutter = VideoCutter(self.video_path, output_dir=final_output_dir)
            
            def cut_progress(current, total):
                if total == 100:
                    self.update_progress(current, total, "Fase 2: Renderizando vídeo")
                else:
                    self.update_progress(current, total, "Fase 2: Concluindo pessoa")
                    self.log(f"Pessoa {current}/{total} concluída.")
                
            selected_quality = self.quality_var.get()
            bitrate = self.quality_bitrate_map.get(selected_quality, "5000k")
            
            self.log(f"Qualidade de renderização: {selected_quality} ({bitrate}) | Hardware: {self.hw_var.get()}")
            self.log(f"Modo: {self.mode_var.get()} | Duração máx.: {self.duration_var.get()}s | Câmera lenta até: {self.min_dur_var.get()}s")
            
            stats = cutter.cut_scenes(
                scenes, 
                tracker.fps, 
                bitrate=bitrate, 
                mode=self.mode_var.get(),
                max_duration=float(self.duration_var.get()),
                min_duration=float(self.min_dur_var.get()),
                num_photos=int(self.photos_var.get()),
                hw_accel=self.hw_var.get(),
                preview_mode=self.preview_var.get(),
                progress_callback=cut_progress, 
                frame_callback=self.update_preview,
                cancel_event=self.cancel_event,
                log_callback=self.log
            )
            stats["tracking_time"] = time_phase1
            
            self.after(0, self.plot_performance_chart, stats)
            
            if self.cancel_event.is_set():
                self.log("Processamento cancelado pelo usuário durante a renderização.")
                self.after(0, messagebox.showwarning, "Cancelado", "A renderização foi interrompida. Alguns arquivos podem estar incompletos.")
                return

            total_elapsed = time.time() - t_total_start
            self.log(f"Processamento concluído com sucesso!")
            self.log(f"Tempo total decorrido: {total_elapsed:.2f} segundos.")
            
            sound = self.sound_var.get()
            if sound == "Soft Bell":
                winsound.PlaySound(os.path.join("alertas", "soft_bell.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sound == "Success Chime":
                winsound.PlaySound(os.path.join("alertas", "success_chime.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sound == "Arcade Level Up":
                winsound.PlaySound(os.path.join("alertas", "arcade_level_up.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
            
            self.after(0, self.status_label.configure, {"text": f"Concluído em {total_elapsed:.1f}s!"})
            self.after(0, self.progress_bar.set, 1)
            self.after(0, messagebox.showinfo, "Sucesso", f"Vídeos exportados na pasta:\n{final_output_dir}")
            
        except Exception as e:
            self.log(f"Erro grave: {str(e)}")
            self.after(0, messagebox.showerror, "Erro", f"Ocorreu um erro: {str(e)}")
        finally:
            self.after(0, self._reset_ui)
            
    def plot_performance_chart(self, stats):
        for widget in self.perf_canvas_frame.winfo_children():
            widget.destroy()
            
        fig, ax = plt.subplots(figsize=(6, 4), facecolor="#2b2b2b")
        ax.set_facecolor("#2b2b2b")
        
        mode = self.mode_var.get()
        
        if mode == "Apenas Imagens":
            labels = ['Rastreamento IA', 'Análise e Extração IA']
            times = [stats.get("tracking_time", 0), stats.get("video_render_time", 0) + stats.get("image_export_time", 0)]
            colors = ['#3498db', '#9b59b6']
        else:
            labels = ['Rastreamento IA', 'Renderização MP4', 'Exportação Fotos']
            times = [stats.get("tracking_time", 0), stats.get("video_render_time", 0), stats.get("image_export_time", 0)]
            colors = ['#3498db', '#e74c3c', '#2ecc71']
        
        bars = ax.bar(labels, times, color=colors)
        ax.set_ylabel('Tempo (Segundos)', color='white')
        
        total_seconds = sum(times)
        total_mins = int(total_seconds // 60)
        total_secs = int(total_seconds % 60)
        
        ax.set_title(f'Desempenho Total de Processamento: {total_mins}m {total_secs}s\nPessoas Processadas: {stats.get("processed_persons", 0)} | Fotos: {stats.get("photos_exported", 0)}', color='white')
        ax.tick_params(colors='white')
        
        for bar in bars:
            yval = bar.get_height()
            if yval > 0:
                m = int(yval // 60)
                s = int(yval % 60)
                time_str = f"{int(yval)}s\n({m}m {s}s)" if m > 0 else f"{int(yval)}s"
                ax.text(bar.get_x() + bar.get_width()/2.0, yval, time_str, va='bottom', ha='center', color='white')
        
        for spine in ax.spines.values():
            ax.tick_params(colors='white')
        ax.set_title("Tempos de Processamento (Fases)", color='white')
        
        self.perf_canvas = FigureCanvasTkAgg(fig, master=self.perf_canvas_frame)
        self.perf_canvas.draw()
        self.perf_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Mudar o foco para a aba de desempenho
        self.tabview.set("Relatório de Desempenho")

    def _auto_detect_hardware(self):
        import subprocess
        try:
            out = subprocess.check_output("wmic path win32_VideoController get name", shell=True).decode().upper()
            if "NVIDIA" in out:
                self.hw_var.set("NVIDIA")
            elif "AMD" in out or "RADEON" in out:
                self.hw_var.set("AMD")
            elif "INTEL" in out:
                self.hw_var.set("Intel")
            else:
                self.hw_var.set("CPU")
        except Exception:
            self.hw_var.set("CPU")
            
    def open_settings_window(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("⚙️ Configurações Gerais")
        settings_win.geometry("400x520")
        settings_win.attributes("-topmost", True)
        settings_win.configure(fg_color="#121212")
        
        main_frame = ctk.CTkFrame(settings_win, fg_color="#1C1C1C", corner_radius=8)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text="Modo de Operação:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))
        mode_menu = ctk.CTkOptionMenu(main_frame, variable=self.mode_var, values=["Ambos", "Apenas Vídeo", "Apenas Imagens"], command=self._on_mode_change)
        mode_menu.pack(fill="x", padx=20, pady=(0, 15))
        
        # Frames dinâmicos
        self.video_settings_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.video_settings_frame.pack(fill="x", padx=20, pady=0)
        
        self.bottom_settings_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.bottom_settings_frame.pack(fill="x", padx=20, pady=0)
        
        # Conteúdo do Video Frame
        ctk.CTkLabel(self.video_settings_frame, text="Duração Máxima do Vídeo (s):").pack(anchor="w", pady=(0, 5))
        ctk.CTkOptionMenu(self.video_settings_frame, variable=self.duration_var, values=["10", "15", "20", "30", "40", "50"]).pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.video_settings_frame, text="Duração Mínima / Alvo Câmera Lenta (s):").pack(anchor="w", pady=(0, 5))
        ctk.CTkOptionMenu(self.video_settings_frame, variable=self.min_dur_var, values=["5", "8", "10", "12", "15"]).pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.video_settings_frame, text="Qualidade do Vídeo:").pack(anchor="w", pady=(0, 5))
        ctk.CTkOptionMenu(self.video_settings_frame, variable=self.quality_var, values=list(self.quality_bitrate_map.keys())).pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.video_settings_frame, text="Aceleração de Hardware:").pack(anchor="w", pady=(0, 5))
        ctk.CTkOptionMenu(self.video_settings_frame, variable=self.hw_var, values=["CPU", "NVIDIA", "AMD", "Intel"]).pack(fill="x", pady=(0, 15))
        
        # Conteúdo Inferior
        ctk.CTkLabel(self.bottom_settings_frame, text="Quantidade de Fotos Extraídas:").pack(anchor="w", pady=(0, 5))
        ctk.CTkOptionMenu(self.bottom_settings_frame, variable=self.photos_var, values=["5", "10", "15", "20"]).pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.bottom_settings_frame, text="Sinal Sonoro de Conclusão:").pack(anchor="w", pady=(0, 5))
        sound_frame = ctk.CTkFrame(self.bottom_settings_frame, fg_color="transparent")
        sound_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkOptionMenu(sound_frame, variable=self.sound_var, values=["Nenhum", "Soft Bell", "Success Chime", "Arcade Level Up"]).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(sound_frame, text="🔊", width=40, command=self._play_sound_preview, fg_color="#2A2A2A", hover_color="#3A3A3A", corner_radius=4).pack(side="right")
        
        self._on_mode_change(self.mode_var.get())
        
    def _on_mode_change(self, value):
        if hasattr(self, 'video_settings_frame') and self.video_settings_frame.winfo_exists():
            if value == "Apenas Imagens":
                self.video_settings_frame.pack_forget()
            else:
                self.video_settings_frame.pack(fill="x", padx=20, pady=0, before=self.bottom_settings_frame)
                
    def _play_sound_preview(self):
        sound = self.sound_var.get()
        import winsound
        import os
        if sound == "Soft Bell":
            winsound.PlaySound(os.path.join("alertas", "soft_bell.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sound == "Success Chime":
            winsound.PlaySound(os.path.join("alertas", "success_chime.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sound == "Arcade Level Up":
            winsound.PlaySound(os.path.join("alertas", "arcade_level_up.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
            
    def _reset_ui(self):
        self.process_start_time = None
        self.start_btn.configure(state="normal")
        self.select_btn.configure(state="normal")
        self.output_btn.configure(state="normal")
        self.settings_btn.configure(state="normal")
        if hasattr(self, 'preview_menu'):
            self.preview_menu.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_label.configure(text="Pronto para novo processamento.")
        self.progress_bar.set(0)
        
    def start_processing(self):
        self.start_btn.configure(state="disabled")
        self.select_btn.configure(state="disabled")
        self.output_btn.configure(state="disabled")
        self.settings_btn.configure(state="disabled")
        if hasattr(self, 'preview_menu'):
            self.preview_menu.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        
        self.log("--- Novo Processamento ---")
        thread = threading.Thread(target=self.processing_thread, daemon=True)
        thread.start()

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
