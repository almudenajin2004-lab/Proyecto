import cv2
import numpy as np
from tkinter import filedialog, Tk, simpledialog

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
UMBRAL_VERDE = 240
UNIDAD = "mm"
Y_INICIO, Y_FIN   = 50, 700
X_INICIO, X_FIN   = 50, 1200

Y1, Y2   = 235 , 485
X1, X2   = 390 , 890

# ─────────────────────────────────────────────
# VARIABLES GLOBALES DE CALIBRACIÓN
# ─────────────────────────────────────────────
puntos_calib   = []   # almacena los 2 clics de calibración
factor_escala  = None

def click_calibracion(evento, x, y, flags, param):
    """Captura hasta 2 clics para calibración."""
    global puntos_calib, factor_escala
    if evento == cv2.EVENT_LBUTTONDOWN and len(puntos_calib) < 2:
        puntos_calib.append((x, y))
        cv2.circle(param, (x, y), 6, (0, 165, 255), -1)   # punto naranja
        cv2.imshow("CALIBRACION - haz clic en 2 puntos", param)

        if len(puntos_calib) == 2:
            px = abs(puntos_calib[1][0] - puntos_calib[0][0])
            py = abs(puntos_calib[1][1] - puntos_calib[0][1])
            distancia_px = np.hypot(px, py)   # distancia euclidiana

            # Dibuja línea entre los dos puntos
            cv2.line(param, puntos_calib[0], puntos_calib[1], (0, 165, 255), 1)
            cv2.putText(param, f"{distancia_px:.1f} px",
                        (puntos_calib[0][0], puntos_calib[0][1] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            cv2.imshow("CALIBRACION - haz clic en 2 puntos", param)

            # Pide la medida real mediante teclado
            root_tmp = Tk()
            root_tmp.withdraw()
            medida_real = simpledialog.askfloat(
                "Medida real",
                f"Distancia entre los 2 puntos: {distancia_px:.1f} px\n"
                f"¿Cuánto mide eso en {UNIDAD}?",
                minvalue=0.001,
                parent=root_tmp
            )
            root_tmp.destroy()

            if medida_real:
                factor_escala = medida_real / distancia_px
                print(f"\n[CALIBRACIÓN OK]")
                print(f"  {distancia_px:.1f} px  →  {medida_real} {UNIDAD}")
                print(f"  Factor = {factor_escala:.5f} {UNIDAD}/px")
            else:
                print("[Calibración cancelada]")

            cv2.destroyWindow("CALIBRACION - haz clic en 2 puntos")

# ─────────────────────────────────────────────
# SELECCIÓN DE IMAGEN
# ─────────────────────────────────────────────
root = Tk()
root.withdraw()
ruta = filedialog.askopenfilename(
    title="Selecciona la imagen",
    filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp")]
)
root.destroy()

if not ruta:
    print("No seleccionaste ninguna imagen.")
    exit()

img = cv2.imread(ruta)
if img is None:
    print("Error: no se pudo cargar la imagen.")
    exit()

# ─────────────────────────────────────────────
# PASO 1 — CALIBRACIÓN INTERACTIVA
# ─────────────────────────────────────────────
calib_img = img.copy()
cv2.namedWindow("CALIBRACION - haz clic en 2 puntos")
cv2.setMouseCallback("CALIBRACION - haz clic en 2 puntos", click_calibracion, calib_img)

print("="*45)
print(" PASO 1: CALIBRACIÓN")
print(" Haz clic en 2 puntos de la imagen sobre")
print(" un objeto de tamaño conocido.")
print(" Pulsa ENTER o ESC para saltar la calibración.")
print("="*45)

cv2.putText(calib_img, "Clic en 2 puntos de referencia | ENTER=saltar",
            (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
cv2.imshow("CALIBRACION - haz clic en 2 puntos", calib_img)

while True:
    key = cv2.waitKey(50) & 0xFF
    if key in (13, 27):    # ENTER o ESC → saltar calibración
        cv2.destroyWindow("CALIBRACION - haz clic en 2 puntos")
        break
    if factor_escala is not None:  # ya se calculó al hacer 2 clics
        break

# ─────────────────────────────────────────────
# PASO 2 — DETECCIÓN DEL LÁSER (FILTRADO POR ÁREA)
# ─────────────────────────────────────────────
roi = calib_img[Y_INICIO:Y_FIN, X_INICIO:X_FIN]
canal_verde = roi[:, :, 1]

# 1. Binarización
_, thresh = cv2.threshold(canal_verde, UMBRAL_VERDE, 255, cv2.THRESH_BINARY)

# 2. Encontrar TODOS los contornos (lásers reales + reflejos)
contornos, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# 3. EL TRUCO: Ordenar los contornos por su Área (de mayor a menor masa)
contornos_ordenados = sorted(contornos, key=cv2.contourArea, reverse=True)

# 4. Nos quedamos SOLO con los 2 más grandes (ignorando todo el ruido restante)
# Si encuentra menos de 2, cogerá los que haya.
contornos_principales = contornos_ordenados[:2] 

thresh = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

centros = []
for cnt in contornos_principales:
    M = cv2.moments(cnt)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        centros.append((cx, cy))
        
        # Opcional: Dibujar el contorno exacto detectado para que veas qué masa escogió
        cv2.drawContours(roi, [cnt], -1, (0, 255, 0), 1)
        # Dibujar el centro de masa

        # 1. Dibujar el círculo exterior (HUECO)
        cv2.circle(roi, (cx, cy), 7, (0, 0, 255), 2)
        
        # 2. Dibujar el puntito central (MACIZO)
        cv2.circle(roi, (cx, cy), 2, (0, 0, 255), -1)

        # Dibujar el centro
        cv2.circle(thresh, (cx, cy), 5, (255, 0, 0), -1)

print("\n" + "="*45)
print(" PASO 2: DETECCIÓN DE LÁSER")

if len(centros) >= 2:
    # Ordenamos por la coordenada X (de izquierda a derecha) para tener p1 y p2 siempre en el mismo orden
    centros.sort()
    p1, p2 = centros[0], centros[1]
    
    # Cálculo de distancia
    distancia_px = np.hypot(p2[0]-p1[0], p2[1]-p1[1])

    # Dibuja línea y etiqueta entre los dos puntos
    cv2.line(roi, p1, p2, (0, 255, 255), 1)
    cv2.line(thresh, p1, p2, (255, 0, 0), 1)

    print(f"  Puntos detectados : {len(centros)}")
    print(f"  Distancia         : {distancia_px:.1f} px")

    if factor_escala:
        distancia_real = distancia_px * factor_escala
        etiqueta = f"{distancia_real:.2f} {UNIDAD}"
        print(f"  Factor de escala  : {factor_escala:.5f} {UNIDAD}/px")
        print(f"  Distancia real    : {distancia_real:.2f} {UNIDAD}")
    else:
        etiqueta = f"{distancia_px:.1f} px"
        print("  (sin calibración, resultado en px)")

    cv2.putText(roi, etiqueta,
                (p1[0], p1[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.putText(thresh, etiqueta,
                (p1[0], p1[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
else:
    print(f"  Solo se detectaron {len(centros)} puntos grandes. Se necesitan 2.")
    print("  Ajusta UMBRAL_VERDE o revisa la iluminación.")

print("="*45)

# ─────────────────────────────────────────────
# PASO 3 — MOSTRAR RESULTADO
# ─────────────────────────────────────────────
cv2.imshow("Resultado (ROI)", roi)
thresh = thresh[Y1:Y2, X1:X2]
cv2.imshow("Mascara canal verde", thresh)
cv2.waitKey(0)
cv2.destroyAllWindows()