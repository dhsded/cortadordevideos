import cv2
import numpy as np
from PIL import Image

def _pil_to_cv(pil_img):
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def _cv_to_pil(cv_img):
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

def apply_hdr_clahe(img, clip_limit=2.0, tile_grid_size=(8, 8)):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_eq = clahe.apply(l)
    lab_eq = cv2.merge((l_eq, a, b))
    return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

def apply_clarity(img, intensity=1.5):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    # Usar filtro bilateral para borrar sem destruir bordas
    l_blur = cv2.bilateralFilter(l, 9, 75, 75)
    l_sharp = cv2.addWeighted(l, 1.0 + intensity, l_blur, -intensity, 0)
    lab_sharp = cv2.merge((l_sharp, a, b))
    return cv2.cvtColor(lab_sharp, cv2.COLOR_LAB2BGR)

def apply_halation_bloom(img, thresh=200, blur_radius=21, intensity=0.5):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[:,:,2]
    mask = cv2.threshold(v, thresh, 255, cv2.THRESH_BINARY)[1]
    
    highlights = cv2.bitwise_and(img, img, mask=mask)
    bloom = cv2.GaussianBlur(highlights, (blur_radius, blur_radius), 0)
    
    # Mistura tipo "Screen"
    img_f = img.astype(np.float32) / 255.0
    bloom_f = bloom.astype(np.float32) / 255.0 * intensity
    screen = 1.0 - (1.0 - img_f) * (1.0 - bloom_f)
    return (np.clip(screen, 0, 1) * 255).astype(np.uint8)

def apply_teal_orange(img):
    b, g, r = cv2.split(img)
    l = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    l_inv = 255 - l
    
    # Sombras ficam com tom Azul/Ciano (Teal)
    b = cv2.addWeighted(b, 1.0, l_inv, 0.25, 0)
    g = cv2.addWeighted(g, 1.0, l_inv, 0.1, 0)
    
    # Luzes ficam Quentes (Orange)
    r = cv2.addWeighted(r, 1.0, l, 0.35, 0)
    g = cv2.addWeighted(g, 1.0, l, 0.15, 0)
    
    merged = cv2.merge((b, g, r))
    hsv = cv2.cvtColor(merged, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = cv2.multiply(s, 0.85) # Reduzir ligeiramente a saturação para não ficar artificial
    hsv = cv2.merge((h, s, v))
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

# ---- PRO FILTERS (PUBLIC) ----

def filter_pro_arri_alexa(pil_img):
    cv_img = _pil_to_cv(pil_img)
    cv_img = apply_hdr_clahe(cv_img, clip_limit=1.5)
    cv_img = apply_teal_orange(cv_img)
    cv_img = apply_clarity(cv_img, intensity=0.5)
    return _cv_to_pil(cv_img)

def filter_pro_g_master(pil_img):
    cv_img = _pil_to_cv(pil_img)
    cv_img = apply_clarity(cv_img, intensity=2.0)
    cv_img = apply_hdr_clahe(cv_img, clip_limit=2.5)
    return _cv_to_pil(cv_img)

def filter_pro_kodak(pil_img):
    cv_img = _pil_to_cv(pil_img)
    cv_img = apply_halation_bloom(cv_img, thresh=180, blur_radius=35, intensity=0.6)
    cv_img = apply_hdr_clahe(cv_img, clip_limit=1.2)
    b, g, r = cv2.split(cv_img)
    r = cv2.addWeighted(r, 1.1, np.zeros_like(r), 0, 10) # Esquentar globalmente
    b = cv2.addWeighted(b, 0.9, np.zeros_like(b), 0, 0)
    cv_img = cv2.merge((b, g, r))
    return _cv_to_pil(cv_img)

def filter_pro_leica_monochrom(pil_img):
    cv_img = _pil_to_cv(pil_img)
    lab = cv2.cvtColor(cv_img, cv2.COLOR_BGR2LAB)
    l, _, _ = cv2.split(lab)
    l_float = l.astype(np.float32) / 255.0
    l_contrast = np.clip((l_float - 0.5) * 1.5 + 0.5, 0, 1) * 255.0
    l_contrast = l_contrast.astype(np.uint8)
    cv_img = cv2.merge((l_contrast, l_contrast, l_contrast))
    cv_img = apply_clarity(cv_img, intensity=1.0)
    return _cv_to_pil(cv_img)

def filter_pro_fuji_velvia(pil_img):
    cv_img = _pil_to_cv(pil_img)
    cv_img = apply_hdr_clahe(cv_img, clip_limit=1.5)
    hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    s = cv2.multiply(s, 1.4)
    v = cv2.multiply(v, 1.1)
    hsv = cv2.merge((h, s, v))
    cv_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    b, g, r = cv2.split(cv_img)
    r = cv2.addWeighted(r, 1.05, np.zeros_like(r), 0, 0)
    b = cv2.addWeighted(b, 1.05, np.zeros_like(b), 0, 0)
    cv_img = cv2.merge((b, g, r))
    cv_img = apply_clarity(cv_img, intensity=0.5)
    return _cv_to_pil(cv_img)

def filter_pro_drone_dji(pil_img):
    cv_img = _pil_to_cv(pil_img)
    cv_img = apply_clarity(cv_img, intensity=1.5)
    hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(hsv, np.array([90, 50, 50]), np.array([130, 255, 255]))
    blue_mask_f = cv2.GaussianBlur(blue_mask, (21, 21), 0).astype(np.float32) / 255.0
    v = hsv[:,:,2].astype(np.float32)
    v = v * (1.0 - (blue_mask_f * 0.4))
    hsv[:,:,2] = np.clip(v, 0, 255).astype(np.uint8)
    cv_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    cv_img = apply_hdr_clahe(cv_img, clip_limit=2.0)
    return _cv_to_pil(cv_img)

def filter_pro_sunset_golden_hour(pil_img):
    cv_img = _pil_to_cv(pil_img)
    cv_img = apply_halation_bloom(cv_img, thresh=150, blur_radius=41, intensity=0.7)
    b, g, r = cv2.split(cv_img)
    r = cv2.addWeighted(r, 1.2, np.zeros_like(r), 0, 20)
    g = cv2.addWeighted(g, 1.05, np.zeros_like(g), 0, 5)
    b = cv2.addWeighted(b, 0.8, np.zeros_like(b), 0, -10)
    cv_img = cv2.merge((b, g, r))
    cv_img = apply_clarity(cv_img, intensity=0.3)
    return _cv_to_pil(cv_img)
