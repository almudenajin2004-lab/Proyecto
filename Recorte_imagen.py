#Recorte_imagen
import cv2

# 1. Cargar la imagen
img = cv2.imread(r'C:\Users\Almudena\OneDrive\Escritorio\EONSEA\Percepcion\B2.jpeg')
alto, ancho = img.shape[:2] # 720, 1280

# 2. Definir el tamaño del recorte deseado
w_recorte, h_recorte = 500, 250 

# 3. Calcular coordenadas (asegurando valores enteros)
cx, cy = ancho // 2, alto // 2

x1 = cx - (w_recorte // 2)
x2 = cx + (w_recorte // 2)
y1 = cy - (h_recorte // 2)
y2 = cy + (h_recorte // 2)

# 4. Realizar el recorte (Slicing: [filas, columnas])
# ¡Ojo! En Numpy primero va el eje Y (alto) y luego el X (ancho)
recorte = img[y1:y2, x1:x2]

# Mostrar resultados
# Si quieres imprimir las coordenadas de recorte que calculaste antes:
print(f"Recorte realizado en: X({x1} , {x2}), Y({y1} , {y2})")
cv2.imshow('Recorte Laser', recorte)
cv2.waitKey(0)