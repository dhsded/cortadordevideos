import customtkinter as ctk
from tkinter import filedialog
import multiprocessing
from flow_browser import abrir_navegador_flow

class FlowEditorUI(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("Editor Flow IA")
        self.geometry("600x500")
        self.resizable(False, False)
        
        self.output_dir = ""
        self.prompt_padrao = "Melhore a nitidez e a iluminação. Mantenha o cenário e a roupa idênticos. Aspecto profissional."
        
        self._build_ui()
        
        # Garante que a janela fica focada ao abrir
        self.focus()
        
    def _build_ui(self):
        # Título
        title_label = ctk.CTkLabel(self, text="Fotógrafo de IA - Editor Flow", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.pack(pady=(20, 10))
        
        # Descrição
        desc_label = ctk.CTkLabel(self, text="Automatize a melhoria das suas fotos usando o Google Labs Flow.", font=ctk.CTkFont(size=12))
        desc_label.pack(pady=(0, 20))
        
        # Seleção de Pasta
        pasta_frame = ctk.CTkFrame(self)
        pasta_frame.pack(fill="x", padx=20, pady=10)
        
        self.lbl_pasta = ctk.CTkLabel(pasta_frame, text="Nenhuma pasta selecionada (Selecione a pasta de fotos de uma Pessoa)")
        self.lbl_pasta.pack(side="left", padx=10, pady=10)
        
        btn_pasta = ctk.CTkButton(pasta_frame, text="Selecionar Fotos", command=self.selecionar_pasta)
        btn_pasta.pack(side="right", padx=10, pady=10)
        
        # Prompt Padrão
        prompt_label = ctk.CTkLabel(self, text="Prompt Padrão para Injeção:", anchor="w")
        prompt_label.pack(fill="x", padx=20, pady=(10, 0))
        
        self.textbox_prompt = ctk.CTkTextbox(self, height=100)
        self.textbox_prompt.pack(fill="x", padx=20, pady=5)
        self.textbox_prompt.insert("0.0", self.prompt_padrao)
        
        # Botões de Ação
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=30)
        
        btn_espião = ctk.CTkButton(action_frame, text="🕵️‍♂️ Abrir Flow (Modo Espião)", fg_color="#E67E22", hover_color="#D35400", command=self.abrir_espião)
        btn_espião.pack(side="left", expand=True, padx=10)
        
        self.btn_injetar = ctk.CTkButton(action_frame, text="🚀 Injetar Fotos", fg_color="#27AE60", hover_color="#2ECC71", state="disabled")
        self.btn_injetar.pack(side="right", expand=True, padx=10)
        
    def selecionar_pasta(self):
        diretorio = filedialog.askdirectory(title="Selecione a pasta com as Fotos TOP 5")
        if diretorio:
            self.output_dir = diretorio
            self.lbl_pasta.configure(text=f".../{diretorio.split('/')[-1]}")
            
    def abrir_espião(self):
        # Abre o navegador em um processo separado para não travar a UI principal
        p = multiprocessing.Process(target=abrir_navegador_flow)
        p.start()
        # Nota: no futuro, com o HTML em mãos, destravaremos o botão de injetar fotos.
