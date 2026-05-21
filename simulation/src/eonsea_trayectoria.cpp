#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <nav_msgs/msg/odometry.hpp>

#include <cmath>
#include <vector>
#include <string>

// ─────────────────────────────────────────────────────────────────────────────
//  Generador de trayectorias para USV de doble hélice
//
//  Publica secuencias de cmd_vel para validar el controlador bajo distintos
//  patrones de movimiento. Cada "fase" dura un tiempo fijo y avanza
//  automáticamente a la siguiente.
//
//  Perfiles disponibles (parámetro  trajectory_profile):
//    "recta"     — aceleración, crucero y frenada en línea recta
//    "giro"      — giro en el sitio izquierda y derecha
//    "cuadrado"  — cuatro tramos rectos + cuatro giros de 90°
//    "ocho"      — figura en ocho (dos arcos en sentidos opuestos)
//    "slalom"    — zig-zag con velocidad de avance constante
// ─────────────────────────────────────────────────────────────────────────────

struct Fase {
  double vel_lineal;
  double vel_angular;
  double duracion_s;
  std::string etiqueta;
};

static std::vector<Fase> construirPerfil(const std::string & nombre)
{
  if (nombre == "giro") {
    return {
      {0.0,  0.0, 2.0,  "espera"},
      {0.0,  0.4, 4.0,  "giro_izquierda"},
      {0.0,  0.0, 1.0,  "pausa"},
      {0.0, -0.4, 4.0,  "giro_derecha"},
      {0.0,  0.0, 2.0,  "parada"},
    };
  }

  if (nombre == "cuadrado") {
    return {
      {0.5,  0.0,  20.0, "tramo_norte"},
      {0.0,  0.3,   5.2, "giro_este"},
      {0.5,  0.0,  20.0, "tramo_este"},
      {0.0,  0.3,   5.2, "giro_sur"},
      {0.5,  0.0,  20.0, "tramo_sur"},
      {0.0,  0.3,   5.2, "giro_oeste"},
      {0.5,  0.0,  20.0, "tramo_oeste"},
      {0.0,  0.3,   5.2, "giro_origen"},
      {0.0,  0.0,   3.0, "parada"},
    };
  }

  if (nombre == "ocho") {
    const double v = 0.4, w = 0.16, dur = 19.6;
    return {
      {v,  w,   dur, "arco_izquierda_1"},
      {v,  w,   dur, "arco_izquierda_2"},
      {v, -w,   dur, "arco_derecha_1"},
      {v, -w,   dur, "arco_derecha_2"},
      {0.0, 0.0, 3.0, "parada"},
    };
  }

  if (nombre == "slalom") {
    std::vector<Fase> fases;
    const double v = 0.4, w = 0.25, t_recto = 5.0, t_giro = 3.0;
    for (int i = 0; i < 4; ++i) {
      fases.push_back({v, 0.0, t_recto, "recto_" + std::to_string(i + 1)});
      fases.push_back({v, (i % 2 == 0 ? w : -w), t_giro,
                       std::string(i % 2 == 0 ? "desvio_izquierda_" : "desvio_derecha_")
                         + std::to_string(i + 1)});
    }
    fases.push_back({0.0, 0.0, 3.0, "parada"});
    return fases;
  }

  // Recta (por defecto)
  return {
    {0.0,  0.0,  2.0,  "reposo"},
    {0.3,  0.0,  5.0,  "aceleracion"},
    {0.6,  0.0, 15.0,  "crucero"},
    {0.3,  0.0,  5.0,  "desaceleracion"},
    {0.0,  0.0,  3.0,  "parada"},
  };
}

class GeneradorTrayectoria : public rclcpp::Node
{
public:
  GeneradorTrayectoria() : Node("eonsea_trayectoria")
  {
    this->declare_parameter("trajectory_profile", std::string("recta"));
    this->declare_parameter("loop_trajectory",    false);

    std::string perfil = this->get_parameter("trajectory_profile").as_string();
    bucle_  = this->get_parameter("loop_trajectory").as_bool();
    fases_  = construirPerfil(perfil);

    RCLCPP_INFO(this->get_logger(),
      "Generador de trayectorias — perfil: '%s', fases: %zu, bucle: %s",
      perfil.c_str(), fases_.size(), bucle_ ? "si" : "no");

    pub_cmd_vel_ = this->create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 10);
    sub_odom_    = this->create_subscription<nav_msgs::msg::Odometry>(
      "/model/barco_EONSEA/odometry", 10,
      std::bind(&GeneradorTrayectoria::odomCallback, this, std::placeholders::_1));

    t_inicio_      = this->now();
    t_inicio_fase_ = this->now();

    timer_ = this->create_wall_timer(
      std::chrono::milliseconds(100),
      std::bind(&GeneradorTrayectoria::timerCallback, this));
  }

private:
  std::vector<Fase> fases_;
  std::size_t       idx_fase_      = 0;
  bool              bucle_         = false;
  bool              terminado_     = false;
  rclcpp::Time      t_inicio_;
  rclcpp::Time      t_inicio_fase_;

  double pos_x_ = 0.0, pos_y_ = 0.0, guiniada_ = 0.0;
  double dist_  = 0.0, prev_x_ = 0.0, prev_y_ = 0.0;
  bool   primera_odom_ = true;

  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr  pub_cmd_vel_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr sub_odom_;
  rclcpp::TimerBase::SharedPtr                             timer_;

  void odomCallback(const nav_msgs::msg::Odometry::SharedPtr msg)
  {
    pos_x_ = msg->pose.pose.position.x;
    pos_y_ = msg->pose.pose.position.y;
    auto & q = msg->pose.pose.orientation;
    guiniada_ = std::atan2(2.0*(q.w*q.z + q.x*q.y),
                           1.0 - 2.0*(q.y*q.y + q.z*q.z));
    if (primera_odom_) { prev_x_ = pos_x_; prev_y_ = pos_y_; primera_odom_ = false; }
    dist_   += std::hypot(pos_x_ - prev_x_, pos_y_ - prev_y_);
    prev_x_  = pos_x_; prev_y_ = pos_y_;
  }

  void timerCallback()
  {
    if (terminado_) { publicarStop(); return; }

    rclcpp::Time ahora      = this->now();
    double elapsed_fase     = (ahora - t_inicio_fase_).seconds();
    const Fase & fase       = fases_[idx_fase_];

    if (elapsed_fase >= fase.duracion_s) {
      RCLCPP_INFO(this->get_logger(),
        "Fase [%s] completada — pos=(%.2f, %.2f) rumbo=%.1f deg dist=%.2fm",
        fase.etiqueta.c_str(), pos_x_, pos_y_, guiniada_*180.0/M_PI, dist_);

      idx_fase_++;
      if (idx_fase_ >= fases_.size()) {
        if (bucle_) {
          idx_fase_ = 0; dist_ = 0.0;
          RCLCPP_INFO(this->get_logger(), "Repitiendo trayectoria en bucle.");
        } else {
          RCLCPP_INFO(this->get_logger(),
            "Trayectoria completada — distancia total: %.2f m", dist_);
          terminado_ = true; publicarStop(); return;
        }
      }
      t_inicio_fase_ = ahora;
    }

    geometry_msgs::msg::Twist cmd;
    cmd.linear.x  = fases_[idx_fase_].vel_lineal;
    cmd.angular.z = fases_[idx_fase_].vel_angular;
    pub_cmd_vel_->publish(cmd);

    double t_total = (ahora - t_inicio_).seconds();
    if (std::fmod(t_total, 5.0) < 0.12) {
      RCLCPP_INFO(this->get_logger(),
        "[Fase %zu/%zu '%s'] t=%.1fs | pos=(%.2f, %.2f) | rumbo=%.1f deg | dist=%.2fm",
        idx_fase_+1, fases_.size(), fases_[idx_fase_].etiqueta.c_str(),
        t_total, pos_x_, pos_y_, guiniada_*180.0/M_PI, dist_);
    }
  }

  void publicarStop()
  {
    geometry_msgs::msg::Twist cmd;
    pub_cmd_vel_->publish(cmd);
  }
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<GeneradorTrayectoria>());
  rclcpp::shutdown();
  return 0;
}