#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float64.hpp>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <iostream>
#include <string>
#include <algorithm>

// --- CONFIGURACIÓN DE TÓPICOS ---
const std::string TOPIC_MOTOR_IZQ = "/model/barco_EONSEA/joint/motor_izquierdo_joint/cmd_thrust";
const std::string TOPIC_MOTOR_DER = "/model/barco_EONSEA/joint/motor_derecho_joint/cmd_thrust";

// --- PARÁMETROS DE CONTROL ---
const double MAX_THRUST = 2000.0;
const double MAX_THRUST_TURBO = 3000.0;
const double INCREMENT_NORMAL = 80.0;
const double INCREMENT_TURBO = 200.0;
const double INCREMENT_FINE = 20.0;
const double DECAY = 60.0;

const std::string BANNER = 
"╔══════════════════════════════════════════════════╗\n"
"║          PANEL DE CONTROL  ·  EONSEA USV         ║\n"
"╠══════════════════════════════════════════════════╣\n"
"║  W/S      Avanzar / Retroceder                   ║\n"
"║  A/D      Girar izquierda / derecha              ║\n"
"║  SHIFT+W  TURBO                                  ║\n"
"║  1 / 2    Ajuste fino iz / dcha                  ║\n"
"║  ESPACIO  Freno de emergencia                    ║\n"
"║  Ctrl+C   Apagar y salir                         ║\n"
"╚══════════════════════════════════════════════════╝\n";

// Función mágica para leer el teclado sin bloquear la terminal en C++
int getch() {
    int ch;
    struct termios oldt, newt;
    tcgetattr(STDIN_FILENO, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);
    
    // Hacemos que la lectura no sea bloqueante
    int oldf = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, oldf | O_NONBLOCK);
    
    ch = getchar();
    
    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    fcntl(STDIN_FILENO, F_SETFL, oldf);
    return ch;
}

class EonseaTeleop : public rclcpp::Node {
public:
    EonseaTeleop() : Node("eonsea_teleop"), left_thrust_(0.0), right_thrust_(0.0), mode_("NORMAL") {
        
        auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable();
        
        pub_left_ = this->create_publisher<std_msgs::msg::Float64>(TOPIC_MOTOR_IZQ, qos);
        pub_right_ = this->create_publisher<std_msgs::msg::Float64>(TOPIC_MOTOR_DER, qos);
        
        // Timer a 10Hz (100ms)
        timer_ = this->create_wall_timer(
            std::chrono::milliseconds(100),
            std::bind(&EonseaTeleop::timer_callback, this)
        );
        
        std::cout << "\033[2J\033[1;1H"; // Limpiar pantalla
        std::cout << BANNER << std::endl;
    }

    void shutdown_motors() {
        left_thrust_ = 0.0;
        right_thrust_ = 0.0;
        publish_thrust();
        std::cout << "\n[EONSEA] ¡Motores apagados. Hasta luego!" << std::endl;
    }

private:
    void timer_callback() {
        int c = EOF;
        int temp;
        
        // ¡EL TRUCO MÁGICO! 
        // Leemos todas las teclas atascadas en el buffer rapidísimo
        // y nos quedamos solo con la última que pulsaste.
        while ((temp = getch()) != EOF) {
            c = temp;
        }
        
        if (c == 3) { // 3 es el código ASCII para Ctrl+C
            shutdown_motors();
            rclcpp::shutdown();
            return;
        }

        if (c == 'W') {
            apply_control(c, MAX_THRUST_TURBO, INCREMENT_TURBO);
            mode_ = "TURBO";
        } else if (c != EOF) {
            apply_control(c, MAX_THRUST, INCREMENT_NORMAL);
            mode_ = "ARRANQUE";
        } else {
            apply_friction();
            mode_ = "PARADO";
        }

        publish_thrust();
        print_status();
    }

    void apply_control(int key, double max_t, double inc) {
        if (key == 'w' || key == 'W') {
            left_thrust_ = std::min(left_thrust_ + inc, max_t);
            right_thrust_ = std::min(right_thrust_ + inc, max_t);
        } else if (key == 's') {
            left_thrust_ = std::max(left_thrust_ - inc, -max_t);
            right_thrust_ = std::max(right_thrust_ - inc, -max_t);
        } else if (key == 'a') {
            right_thrust_ = std::min(right_thrust_ + inc, max_t);
            left_thrust_ = std::max(left_thrust_ - inc, -max_t);
        } else if (key == 'd') {
            left_thrust_ = std::min(left_thrust_ + inc, max_t);
            right_thrust_ = std::max(right_thrust_ - inc, -max_t);
        } else if (key == '1') {
            left_thrust_ = std::max(left_thrust_ - INCREMENT_FINE, -max_t);
            right_thrust_ = std::min(right_thrust_ + INCREMENT_FINE, max_t);
        } else if (key == '2') {
            left_thrust_ = std::min(left_thrust_ + INCREMENT_FINE, max_t);
            right_thrust_ = std::max(right_thrust_ - INCREMENT_FINE, -max_t);
        } else if (key == ' ') {
            left_thrust_ = 0.0;
            right_thrust_ = 0.0;
        }
    }

    void apply_friction() {
        if (left_thrust_ > 0) left_thrust_ = std::max(0.0, left_thrust_ - DECAY);
        else if (left_thrust_ < 0) left_thrust_ = std::min(0.0, left_thrust_ + DECAY);

        if (right_thrust_ > 0) right_thrust_ = std::max(0.0, right_thrust_ - DECAY);
        else if (right_thrust_ < 0) right_thrust_ = std::min(0.0, right_thrust_ + DECAY);
    }

    void publish_thrust() {
        std_msgs::msg::Float64 msg_l, msg_r;
        msg_l.data = left_thrust_;
        msg_r.data = right_thrust_;
        pub_left_->publish(msg_l);
        pub_right_->publish(msg_r);
    }

    void print_status() {
        printf("\r[Modo: %-6s] Potencia -> Izq: %6.1f | Der: %6.1f   ", 
               mode_.c_str(), left_thrust_, right_thrust_);
        fflush(stdout);
    }

    rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr pub_left_;
    rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr pub_right_;
    rclcpp::TimerBase::SharedPtr timer_;
    
    double left_thrust_;
    double right_thrust_;
    std::string mode_;
};

int main(int argc, char * argv[]) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<EonseaTeleop>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}