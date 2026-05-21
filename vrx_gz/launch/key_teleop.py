import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
import sys
import select
import termios
import tty

# --- CONFIGURACIÓN DE TU BARCO ---
MAX_THRUST = 2000.0   # Potencia máxima
INCREMENT = 100.0     # Cuánto acelera por cada instante que pulsas la tecla
DECAY = 50.0          # Cuánto frena por la "fricción" del agua al soltar la tecla

msg = """
🌊 PANEL DE CONTROL EONSEA 🌊
---------------------------
Mantén pulsado para mover:
        W (Acelerar)
A (Izquierda)  S (Atrás)  D (Derecha)

[ESPACIO] : Freno de emergencia (Ancla)
Q         : Apagar motores y salir
---------------------------
"""

def getKey(settings):
    tty.setraw(sys.stdin.fileno())
    # Espera 0.1 segundos a ver si pulsas algo
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

class BoatTeleop(Node):
    def __init__(self):
        super().__init__('boat_teleop')
        # Creamos los publicadores para los motores
        self.pub_left = self.create_publisher(Float64, '/wamv/thrusters/left/thrust', 10)
        self.pub_right = self.create_publisher(Float64, '/wamv/thrusters/right/thrust', 10)
        
        self.left_thrust = 0.0
        self.right_thrust = 0.0
        
        # Un temporizador que envía la potencia 10 veces por segundo (como nuestro antiguo -r 10)
        self.timer = self.create_timer(0.1, self.publish_thrust)

    def publish_thrust(self):
        msg_left = Float64()
        msg_left.data = float(self.left_thrust)
        self.pub_left.publish(msg_left)
        
        msg_right = Float64()
        msg_right.data = float(self.right_thrust)
        self.pub_right.publish(msg_right)

def main(args=None):
    rclpy.init(args=args)
    settings = termios.tcgetattr(sys.stdin)
    node = BoatTeleop()

    print(msg)

    try:
        while rclpy.ok():
            key = getKey(settings)
            
            # LÓGICA DE ACELERACIÓN GRADUAL
            if key == 'w':
                node.left_thrust = min(node.left_thrust + INCREMENT, MAX_THRUST)
                node.right_thrust = min(node.right_thrust + INCREMENT, MAX_THRUST)
            elif key == 's':
                node.left_thrust = max(node.left_thrust - INCREMENT, -MAX_THRUST)
                node.right_thrust = max(node.right_thrust - INCREMENT, -MAX_THRUST)
            elif key == 'a':
                node.left_thrust = max(node.left_thrust - INCREMENT, -MAX_THRUST)
                node.right_thrust = min(node.right_thrust + INCREMENT, MAX_THRUST)
            elif key == 'd':
                node.left_thrust = min(node.left_thrust + INCREMENT, MAX_THRUST)
                node.right_thrust = max(node.right_thrust - INCREMENT, -MAX_THRUST)
            elif key == ' ': # Espacio = Freno de emergencia
                node.left_thrust = 0.0
                node.right_thrust = 0.0
            elif key == 'q': # Salir
                break
                
            # LÓGICA DE FRICCIÓN (Si no pulsas nada, el barco va frenando solo)
            elif key == '':
                if node.left_thrust > 0: node.left_thrust = max(0.0, node.left_thrust - DECAY)
                elif node.left_thrust < 0: node.left_thrust = min(0.0, node.left_thrust + DECAY)
                
                if node.right_thrust > 0: node.right_thrust = max(0.0, node.right_thrust - DECAY)
                elif node.right_thrust < 0: node.right_thrust = min(0.0, node.right_thrust + DECAY)

            # Imprimir la potencia actual en la misma línea
            sys.stdout.write(f"\rPotencia -> Izq: {node.left_thrust:6.1f} | Der: {node.right_thrust:6.1f}")
            sys.stdout.flush()

            rclpy.spin_once(node, timeout_sec=0.0)

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        # Al salir, apagar motores
        node.left_thrust = 0.0
        node.right_thrust = 0.0
        node.publish_thrust()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()
        print("\n¡Motores apagados!")

if __name__ == '__main__':
    main()
