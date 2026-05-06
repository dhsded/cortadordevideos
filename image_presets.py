from PIL import Image, ImageEnhance, ImageOps
from pro_filters import filter_pro_arri_alexa, filter_pro_g_master, filter_pro_kodak, filter_pro_leica_monochrom, filter_pro_fuji_velvia, filter_pro_drone_dji, filter_pro_sunset_golden_hour

def tint_image(img, r_mult, g_mult, b_mult):
    if r_mult == 1.0 and g_mult == 1.0 and b_mult == 1.0:
        return img
    # Split the image into individual bands
    r, g, b = img.split()
    r = r.point(lambda i: i * r_mult)
    g = g.point(lambda i: i * g_mult)
    b = b.point(lambda i: i * b_mult)
    return Image.merge('RGB', (r, g, b))

PRESETS = {
    "00. Original (Sem Filtro)": {},

    # --- CINEMÁTICO (Hollywood & Teal/Orange) ---
    "01. Hollywood Clássico": {"brightness": 0.95, "contrast": 1.2, "saturation": 0.9, "tint": (0.95, 1.0, 1.05)},
    "02. Teal & Orange Suave": {"brightness": 1.0, "contrast": 1.15, "saturation": 1.1, "tint": (1.1, 1.0, 0.9)},
    "03. Teal & Orange Extremo": {"brightness": 0.9, "contrast": 1.3, "saturation": 1.3, "tint": (1.2, 0.95, 0.8)},
    "04. Matrix Dark": {"brightness": 0.85, "contrast": 1.3, "saturation": 0.8, "tint": (0.8, 1.2, 0.8)},
    "05. Cyberpunk Neon": {"brightness": 0.95, "contrast": 1.4, "saturation": 1.5, "tint": (1.2, 0.8, 1.2)},
    "06. Sci-Fi Azul": {"brightness": 0.9, "contrast": 1.2, "saturation": 0.85, "tint": (0.8, 0.9, 1.3)},
    "07. Deserto Apocalíptico": {"brightness": 1.05, "contrast": 1.25, "saturation": 0.7, "tint": (1.3, 1.1, 0.7)},
    "08. Drama Sombrio": {"brightness": 0.75, "contrast": 1.4, "saturation": 0.6, "tint": (0.9, 0.9, 1.0)},
    "09. Golden Hour Filme": {"brightness": 1.1, "contrast": 1.1, "saturation": 1.2, "tint": (1.15, 1.05, 0.85)},
    "10. Frio Nórdico": {"brightness": 0.95, "contrast": 1.1, "saturation": 0.7, "tint": (0.85, 0.95, 1.15)},

    # --- VINTAGE & RETRÔ ---
    "11. Kodak Gold": {"brightness": 1.05, "contrast": 1.1, "saturation": 1.15, "tint": (1.1, 1.0, 0.85)},
    "12. Polaroid 90s": {"brightness": 1.15, "contrast": 0.9, "saturation": 0.8, "tint": (1.05, 0.95, 1.0)},
    "13. Fuji Nostalgia": {"brightness": 1.0, "contrast": 0.85, "saturation": 0.9, "tint": (0.9, 1.1, 0.9)},
    "14. Sépia Clássico": {"brightness": 1.0, "contrast": 1.0, "saturation": 0.0, "tint": (1.2, 1.05, 0.8), "bw": True},
    "15. Sépia Antigo (1920)": {"brightness": 0.9, "contrast": 1.3, "saturation": 0.0, "tint": (1.3, 1.1, 0.7), "bw": True},
    "16. VHS Glitch Suave": {"brightness": 0.95, "contrast": 1.2, "saturation": 1.3, "tint": (1.1, 0.9, 1.1)},
    "17. Foto Desbotada": {"brightness": 1.2, "contrast": 0.7, "saturation": 0.6, "tint": (1.0, 1.0, 0.9)},
    "18. Anos 70 Quente": {"brightness": 0.95, "contrast": 1.15, "saturation": 1.2, "tint": (1.2, 1.0, 0.7)},
    "19. Lomo Hipster": {"brightness": 0.85, "contrast": 1.4, "saturation": 1.2, "tint": (0.9, 1.1, 0.8)},
    "20. Câmera Descartável": {"brightness": 1.1, "contrast": 1.2, "saturation": 0.85, "tint": (0.95, 1.05, 1.05), "sharpness": 1.5},

    # --- PRETO E BRANCO ---
    "21. P&B Standard": {"brightness": 1.0, "contrast": 1.0, "saturation": 0.0, "bw": True},
    "22. P&B Alto Contraste": {"brightness": 1.0, "contrast": 1.5, "saturation": 0.0, "bw": True},
    "23. Noir Cinematográfico": {"brightness": 0.8, "contrast": 1.6, "saturation": 0.0, "bw": True},
    "24. P&B Jornalismo": {"brightness": 1.1, "contrast": 1.2, "saturation": 0.0, "bw": True, "sharpness": 1.3},
    "25. P&B Suave / Matte": {"brightness": 1.15, "contrast": 0.8, "saturation": 0.0, "bw": True},
    "26. P&B Sombrio": {"brightness": 0.7, "contrast": 1.3, "saturation": 0.0, "bw": True},
    "27. P&B Prateado": {"brightness": 1.05, "contrast": 1.3, "saturation": 0.0, "tint": (0.95, 0.95, 1.05), "bw": True},
    "28. P&B Ansel Adams": {"brightness": 0.9, "contrast": 1.4, "saturation": 0.0, "bw": True, "sharpness": 1.5},
    "29. P&B Sépia Frio": {"brightness": 0.95, "contrast": 1.1, "saturation": 0.0, "tint": (0.9, 0.95, 1.1), "bw": True},
    "30. P&B Superexposto": {"brightness": 1.3, "contrast": 0.9, "saturation": 0.0, "bw": True},

    # --- RETRATO & PELE ---
    "31. Retrato Natural": {"brightness": 1.05, "contrast": 1.05, "saturation": 1.05, "sharpness": 0.9},
    "32. Glow Suave": {"brightness": 1.1, "contrast": 0.9, "saturation": 0.95, "sharpness": 0.7},
    "33. Bronzeado de Verão": {"brightness": 1.0, "contrast": 1.1, "saturation": 1.2, "tint": (1.1, 1.0, 0.9)},
    "34. Moda Editorial": {"brightness": 1.05, "contrast": 1.25, "saturation": 0.85, "sharpness": 1.2},
    "35. High-Key Luminoso": {"brightness": 1.25, "contrast": 0.85, "saturation": 0.9},
    "36. Low-Key Sombrio": {"brightness": 0.7, "contrast": 1.3, "saturation": 0.9},
    "37. Pele de Porcelana": {"brightness": 1.15, "contrast": 0.95, "saturation": 0.8, "sharpness": 0.8, "tint": (1.0, 1.0, 1.05)},
    "38. Luz de Janela": {"brightness": 1.1, "contrast": 1.15, "saturation": 0.95, "tint": (0.95, 0.95, 1.05)},
    "39. Contraste Dramático": {"brightness": 0.9, "contrast": 1.4, "saturation": 1.1, "sharpness": 1.3},
    "40. Retrato Pêssego": {"brightness": 1.05, "contrast": 1.0, "saturation": 1.1, "tint": (1.1, 1.05, 0.95)},

    # --- PAISAGEM & URBANO ---
    "41. HDR Pop Extremo": {"brightness": 1.0, "contrast": 1.3, "saturation": 1.5, "sharpness": 1.4},
    "42. Floresta Densa": {"brightness": 0.9, "contrast": 1.2, "saturation": 1.1, "tint": (0.9, 1.1, 0.9)},
    "43. Pôr do Sol Fogo": {"brightness": 1.0, "contrast": 1.1, "saturation": 1.3, "tint": (1.2, 1.0, 0.8)},
    "44. Noite Urbana": {"brightness": 0.8, "contrast": 1.3, "saturation": 1.2, "tint": (0.9, 0.9, 1.2)},
    "45. Arquitetura Cinza": {"brightness": 1.0, "contrast": 1.2, "saturation": 0.4},
    "46. Céu Azul Profundo": {"brightness": 0.95, "contrast": 1.1, "saturation": 1.2, "tint": (0.9, 0.95, 1.15)},
    "47. Névoa Fria": {"brightness": 1.1, "contrast": 0.8, "saturation": 0.7, "tint": (0.9, 0.95, 1.1)},
    "48. Dia Quente": {"brightness": 1.1, "contrast": 1.1, "saturation": 1.1, "tint": (1.05, 1.0, 0.95)},
    "49. Monocromático Azul": {"brightness": 0.9, "contrast": 1.2, "saturation": 0.0, "tint": (0.7, 0.8, 1.3), "bw": True},
    "50. Vermelho Marte": {"brightness": 0.9, "contrast": 1.3, "saturation": 1.2, "tint": (1.4, 0.8, 0.8)},
    
    # --- PRO STUDIO (Motores OpenCV) ---
    "PRO: Arri Alexa (Teal & Orange)": {"pro": "arri"},
    "PRO: Lente G-Master (Clarity)": {"pro": "gmaster"},
    "PRO: Kodak Portra 400 (Bloom)": {"pro": "kodak"},
    "PRO: Leica Monochrom (P&B)": {"pro": "leica"},
    "PRO: Fuji Velvia (Paisagem)": {"pro": "velvia"},
    "PRO: Drone DJI (Polarizador)": {"pro": "drone"},
    "PRO: Sunset Golden Hour": {"pro": "golden"},
}

def apply_preset(img, preset_name):
    """
    Applies the selected preset dictionary to the PIL image.
    """
    preset_data = PRESETS.get(preset_name, {})
    if not preset_data:
        return img
        
    if "pro" in preset_data:
        mode = preset_data["pro"]
        if mode == "arri":
            return filter_pro_arri_alexa(img)
        elif mode == "gmaster":
            return filter_pro_g_master(img)
        elif mode == "kodak":
            return filter_pro_kodak(img)
        elif mode == "leica":
            return filter_pro_leica_monochrom(img)
        elif mode == "velvia":
            return filter_pro_fuji_velvia(img)
        elif mode == "drone":
            return filter_pro_drone_dji(img)
        elif mode == "golden":
            return filter_pro_sunset_golden_hour(img)
        
    b = preset_data.get('brightness', 1.0)
    c = preset_data.get('contrast', 1.0)
    s = preset_data.get('saturation', 1.0)
    sh = preset_data.get('sharpness', 1.0)
    tint = preset_data.get('tint', (1.0, 1.0, 1.0))
    bw = preset_data.get('bw', False)
    
    # Processamento
    res = img.copy()
    
    if bw:
        res = ImageOps.grayscale(res).convert('RGB')
        
    if tint != (1.0, 1.0, 1.0):
        res = tint_image(res, *tint)
        
    if b != 1.0:
        res = ImageEnhance.Brightness(res).enhance(b)
    if c != 1.0:
        res = ImageEnhance.Contrast(res).enhance(c)
    if s != 1.0:
        res = ImageEnhance.Color(res).enhance(s)
    if sh != 1.0:
        res = ImageEnhance.Sharpness(res).enhance(sh)
        
    return res
