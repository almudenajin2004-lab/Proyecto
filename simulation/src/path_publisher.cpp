#include <rclcpp/rclcpp.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/path.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <std_srvs/srv/empty.hpp>

// ─────────────────────────────────────────────────────────────────────────────
//  Publicador de trayectoria recorrida para RViz
//
//  Se suscribe a la odometría del barco y va acumulando poses en un
//  nav_msgs/Path que publica de forma continua.  En RViz añade el topic
//  /usv/trayectoria_recorrida con el tipo "Path".
//
//  Servicio:  /usv/limpiar_trayectoria  (std_srvs/Empty)
//  Llámalo para borrar el rastro y empezar uno nuevo:
//      ros2 service call /usv/limpiar_trayectoria std_srvs/srv/Empty
// ─────────────────────────────────────────────────────────────────────────────

class PublicadorTrayectoria : public rclcpp::Node
{
public:
  PublicadorTrayectoria() : Node("path_publisher")
  {
    this->declare_parameter("max_puntos",    5000);   // límite de poses acumuladas
    this->declare_parameter("min_distancia", 0.05);   // distancia mínima entre puntos [m]

    max_puntos_     = this->get_parameter("max_puntos").as_int();
    min_distancia_  = this->get_parameter("min_distancia").as_double();

    // Suscripción a odometría
    sub_odom_ = this->create_subscription<nav_msgs::msg::Odometry>(
      "/model/barco_EONSEA/odometry", 10,
      std::bind(&PublicadorTrayectoria::odomCallback, this, std::placeholders::_1));

    // Publicador de la trayectoria
    pub_path_ = this->create_publisher<nav_msgs::msg::Path>(
      "/usv/trayectoria_recorrida", 10);

    // Servicio para limpiar la trayectoria
    srv_limpiar_ = this->create_service<std_srvs::srv::Empty>(
      "/usv/limpiar_trayectoria",
      std::bind(&PublicadorTrayectoria::limpiarCallback, this,
                std::placeholders::_1, std::placeholders::_2));

    // Publicar el path a 5 Hz aunque no haya datos nuevos
    timer_ = this->create_wall_timer(
      std::chrono::milliseconds(200),
      std::bind(&PublicadorTrayectoria::publicarPath, this));

    path_.header.frame_id = "odom";   // frame de referencia para RViz

    RCLCPP_INFO(this->get_logger(),
      "Publicador de trayectoria listo — topic: /usv/trayectoria_recorrida");
    RCLCPP_INFO(this->get_logger(),
      "Para limpiar el rastro: ros2 service call /usv/limpiar_trayectoria std_srvs/srv/Empty");
  }

private:
  nav_msgs::msg::Path path_;
  int    max_puntos_    = 5000;
  double min_distancia_ = 0.05;
  double prev_x_ = 1e9, prev_y_ = 1e9;   // fuerza insertar el primer punto

  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr sub_odom_;
  rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr        pub_path_;
  rclcpp::Service<std_srvs::srv::Empty>::SharedPtr         srv_limpiar_;
  rclcpp::TimerBase::SharedPtr                             timer_;

  void odomCallback(const nav_msgs::msg::Odometry::SharedPtr msg)
  {
    double x = msg->pose.pose.position.x;
    double y = msg->pose.pose.position.y;

    // Solo añadir punto si el barco se ha movido lo suficiente
    double dist = std::hypot(x - prev_x_, y - prev_y_);
    if (dist < min_distancia_) return;

    geometry_msgs::msg::PoseStamped ps;
    ps.header = msg->header;
    ps.header.frame_id = "odom";
    ps.pose = msg->pose.pose;

    path_.poses.push_back(ps);
    prev_x_ = x; prev_y_ = y;

    // Limitar el número máximo de puntos (descarte FIFO)
    if (static_cast<int>(path_.poses.size()) > max_puntos_) {
      path_.poses.erase(path_.poses.begin());
    }
  }

  void publicarPath()
  {
    path_.header.stamp = this->now();
    pub_path_->publish(path_);
  }

  void limpiarCallback(
    const std::shared_ptr<std_srvs::srv::Empty::Request>  /*req*/,
    std::shared_ptr<std_srvs::srv::Empty::Response> /*res*/)
  {
    path_.poses.clear();
    prev_x_ = 1e9; prev_y_ = 1e9;
    RCLCPP_INFO(this->get_logger(), "Trayectoria limpiada.");
  }
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<PublicadorTrayectoria>());
  rclcpp::shutdown();
  return 0;
}