import cv2
import numpy as np
from tkinter import filedialog, Tk, simpledialog
import json, os

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
UMBRAL_VERDE  = 240
UNIDAD        = "mm"
Y_INICIO, Y_FIN  = 50, 700 
X_INICIO, X_FIN  = 50, 1200

# Guarda el .json en la misma carpeta que el script
DIRECTORIO = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CALIB = os.path.join(DIRECTORIO, "calibracion.json")

# ─────────────────────────────────────────────
# MODELO DE TRIANGULACIÓN
# ─────────────────────────────────────────────
# La relación es lineal:
#   separacion_px = f_px * sep_real_mm / Z_mm
#   → sep_real_mm = separacion_px * Z_mm / f_px
#
# Con 2 ejemplos (sep_px1, Z1) y (sep_px2, Z2) donde conoces
# la separación real de los lásers en la pared (sep_ref_mm):
#   f_px = sep_px * Z / sep_real
# Promediamos los 2 valores de f_px para más robustez.
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# PERSISTENCIA DE CALIBRACIÓN
# ─────────────────────────────────────────────
def guardar_calibracion(datos: dict):
    with open(ARCHIVO_CALIB, "w") as f:
        json.dump(datos, f, indent=2)
    print(f"[Calibración guardada en {ARCHIVO_CALIB}]")

def cargar_calibracion() -> dict | None:
    if os.path.exists(ARCHIVO_CALIB):
        with open(ARCHIVO_CALIB) as f:
            return json.load(f)
    return None

# ─────────────────────────────────────────────
# ESTADO GLOBAL
# ─────────────────────────────────────────────
puntos_calib  = []
calib_datos   = cargar_calibracion()   # intenta cargar calibración previa

if calib_datos:
    print(f"[Calibración cargada] f_px={calib_datos['f_px']:.3f}  "
          f"sep_ref={calib_datos['sep_ref_mm']} {UNIDAD}  "
          f"({calib_datos['n_ejemplos']} ejemplo(s))")

# ─────────────────────────────────────────────
# DETECCIÓN DE PUNTOS LÁSER
# ─────────────────────────────────────────────
def detectar_centros(imagen_bgr):
    """Devuelve los 2 centros de masa más grandes en el canal verde."""
    roi = imagen_bgr[Y_INICIO:Y_FIN, X_INICIO:X_FIN]
    canal_verde = roi[:, :, 1]
    _, thresh = cv2.threshold(canal_verde, UMBRAL_VERDE, 255, cv2.THRESH_BINARY)
    contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:2]

    centros = []
    for cnt in contornos:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            centros.append((cx, cy))
    return centros, roi, thresh

# ─────────────────────────────────────────────
# CALIBRACIÓN CON PARED (acumula ejemplos)
# ─────────────────────────────────────────────
def calibrar_con_pared(img):
    """
    Muestra la imagen, detecta los 2 puntos láser automáticamente,
    pide la distancia Z a la pared y la separación real conocida,
    calcula f_px y lo acumula con ejemplos anteriores.
    """
    global calib_datos

    centros, roi_vis, _ = detectar_centros(img)
    if len(centros) < 2:
        print("[Calibración] No se detectaron 2 puntos. Revisa el umbral.")
        return

    centros.sort()
    p1, p2 = centros[0], centros[1]
    sep_px = np.hypot(p2[0]-p1[0], p2[1]-p1[1])

    # Visualización
    vis = roi_vis.copy()
    cv2.circle(vis, p1, 7, (0, 165, 255), 2)
    cv2.circle(vis, p2, 7, (0, 165, 255), 2)
    cv2.line(vis, p1, p2, (0, 165, 255), 1)
    cv2.putText(vis, f"{sep_px:.1f} px", (p1[0], p1[1]-12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
    cv2.imshow("Calibracion con pared", vis)
    cv2.waitKey(500)

    root_tmp = Tk(); root_tmp.withdraw()

    Z_mm = simpledialog.askfloat(
        "Calibración — distancia Z",
        f"Separación detectada: {sep_px:.1f} px\n\n"
        f"¿A qué distancia (mm) está la pared/objeto de la cámara?",
        minvalue=1.0, parent=root_tmp
    )
    if not Z_mm:
        root_tmp.destroy(); return

    sep_ref_mm = simpledialog.askfloat(
        "Calibración — separación real",
        f"¿Cuánto miden en {UNIDAD} los {sep_px:.1f} px detectados?\n"
        "(Mide físicamente la separación de los puntos en la pared.)",
        minvalue=0.001, parent=root_tmp
    )
    root_tmp.destroy()
    if not sep_ref_mm:
        return

    # f_px para este ejemplo
    f_nuevo = sep_px * Z_mm / sep_ref_mm

    # Acumular: promedio ponderado con ejemplos anteriores
    if calib_datos and "f_px" in calib_datos:
        n  = calib_datos["n_ejemplos"]
        f_anterior = calib_datos["f_px"]
        f_px = (f_anterior * n + f_nuevo) / (n + 1)
        n_total = n + 1
    else:
        f_px    = f_nuevo
        n_total = 1

    calib_datos = {
        "f_px":       round(f_px, 5),
        "sep_ref_mm": sep_ref_mm,
        "n_ejemplos": n_total
    }
    guardar_calibracion(calib_datos)

    print(f"\n[CALIBRACIÓN ACTUALIZADA]")
    print(f"  sep detectada : {sep_px:.1f} px")
    print(f"  Z             : {Z_mm} mm")
    print(f"  sep real      : {sep_ref_mm} mm")
    print(f"  f_px nuevo    : {f_nuevo:.3f}")
    print(f"  f_px acum.    : {f_px:.3f}  ({n_total} ejemplos)")

    cv2.destroyWindow("Calibracion con pared")

# ─────────────────────────────────────────────
# MEDICIÓN REAL USANDO PROFUNDIDAD
# ─────────────────────────────────────────────
def medir_objeto(img, Z_objeto_mm: float):
    """
    Detecta los 2 puntos láser sobre el objeto y calcula
    la dimensión real usando la profundidad Z conocida.
    """
    if not calib_datos or "f_px" not in calib_datos:
        print("[Medición] Primero necesitas calibrar con la pared.")
        return

    centros, roi, thresh = detectar_centros(img)
    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    print("\n" + "="*45)
    print(" MEDICIÓN CON PROFUNDIDAD")

    if len(centros) < 2:
        print(f"  Solo {len(centros)} punto(s). Se necesitan 2.")
        print("  Ajusta UMBRAL_VERDE o la iluminación.")
        print("="*45)
        cv2.imshow("Resultado (ROI)", roi)
        cv2.imshow("Mascara canal verde", thresh_bgr)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        return

    centros.sort()
    p1, p2 = centros[0], centros[1]
    sep_px = np.hypot(p2[0]-p1[0], p2[1]-p1[1])

    # ── FÓRMULA CENTRAL ──────────────────────────
    # dim_real = sep_px * Z_objeto / f_px
    dim_real_mm = sep_px * Z_objeto_mm / calib_datos["f_px"]
    # ─────────────────────────────────────────────

    # Dibujar resultado
    for img_d in [roi, thresh_bgr]:
        cv2.circle(img_d, p1, 7, (0, 0, 255), 2)
        cv2.circle(img_d, p1, 2, (0, 0, 255), -1)
        cv2.circle(img_d, p2, 7, (0, 0, 255), 2)
        cv2.circle(img_d, p2, 2, (0, 0, 255), -1)
        cv2.line(img_d, p1, p2, (0, 255, 255), 1)
        cv2.putText(img_d, f"{dim_real_mm:.2f} {UNIDAD}",
                    (p1[0], p1[1] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)

    print(f"  Puntos detectados : {len(centros)}")
    print(f"  Separación        : {sep_px:.1f} px")
    print(f"  Z objeto          : {Z_objeto_mm} mm")
    print(f"  f_px calibrado    : {calib_datos['f_px']:.3f}")
    print(f"  ► Dimensión real  : {dim_real_mm:.2f} {UNIDAD}")
    print("="*45)

    cv2.imshow("Resultado (ROI)", roi)
    cv2.imshow("Mascara canal verde", thresh_bgr)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# ─────────────────────────────────────────────
# MAIN — menú de modos
# ─────────────────────────────────────────────
root = Tk(); root.withdraw()

modo = simpledialog.askstring(
    "Modo",
    "¿Qué quieres hacer?\n\n"
    "  C  →  Calibrar con la pared\n"
    "  M  →  Medir objeto (necesita Z)\n",
    parent=root
)
root.destroy()

if not modo:
    exit()

ruta = None
root2 = Tk(); root2.withdraw()
ruta = filedialog.askopenfilename(
    title="Selecciona la imagen",
    filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp")],
    parent=root2
)
root2.destroy()

if not ruta:
    print("No seleccionaste imagen.")
    exit()

img = cv2.imread(ruta)
if img is None:
    print("Error: no se pudo cargar la imagen.")
    exit()

if modo.strip().upper() == "C":
    calibrar_con_pared(img)

elif modo.strip().upper() == "M":
    root3 = Tk(); root3.withdraw()
    Z = simpledialog.askfloat(
        "Profundidad",
        f"¿A qué distancia (mm) está el objeto de la cámara?",
        minvalue=1.0, parent=root3
    )
    root3.destroy()
    if Z:
        medir_objeto(img, Z)
    else:
        print("Sin profundidad, no se puede medir.")
else:
    print("Modo no reconocido. Usa C o M.")
