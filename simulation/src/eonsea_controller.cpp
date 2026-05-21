#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <std_msgs/msg/float64.hpp>
#include <std_msgs/msg/bool.hpp>
#include <rcl_interfaces/msg/set_parameters_result.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>

// ─────────────────────────────────────────────────────────────────────────────
//  USV Diferential-Thruster Controller
//  Architecture: two independent PID loops (surge + yaw-rate)
//  Features:
//    · Full PID with integral anti-windup (clamping method)
//    · Derivative low-pass filter  (reduces noise amplification)
//    · Dynamic reconfigure of all gains via ROS 2 parameters
//    · Safety watchdog: cuts thrust if no cmd_vel arrives within timeout
//    · Emergency-stop topic (/usv/emergency_stop)
//    · Telemetry topic (/usv/control_debug) for tuning / logging
// ─────────────────────────────────────────────────────────────────────────────

class UsvController : public rclcpp::Node
{
public:
  UsvController() : Node("eonsea_controller")
  {
    // ── Declare parameters ────────────────────────────────────────────────
    // Surge (linear) PID
    this->declare_parameter("pid_linear.kp",        1500.0);
    this->declare_parameter("pid_linear.ki",          50.0);
    this->declare_parameter("pid_linear.kd",         100.0);
    this->declare_parameter("pid_linear.integral_max", 800.0);  // anti-windup clamp

    // Yaw-rate (angular) PID
    this->declare_parameter("pid_angular.kp",        800.0);
    this->declare_parameter("pid_angular.ki",          20.0);
    this->declare_parameter("pid_angular.kd",          60.0);
    this->declare_parameter("pid_angular.integral_max", 400.0);

    // Derivative low-pass filter coefficient  (0 = off, closer to 1 = heavy filter)
    this->declare_parameter("derivative_filter_coeff", 0.7);

    // Thruster limits [N]
    this->declare_parameter("thrust_max",  2500.0);
    this->declare_parameter("thrust_min", -2500.0);

    // Watchdog: seconds without a cmd_vel before cutting thrust
    this->declare_parameter("cmd_timeout_s", 0.5);

    // ── Subscriptions ─────────────────────────────────────────────────────
    sub_cmd_vel_ = this->create_subscription<geometry_msgs::msg::Twist>(
      "/cmd_vel", 10,
      std::bind(&UsvController::cmdVelCallback, this, std::placeholders::_1));

    sub_odom_ = this->create_subscription<nav_msgs::msg::Odometry>(
      "/model/barco_EONSEA/odometry", 10,
      std::bind(&UsvController::odomCallback, this, std::placeholders::_1));

    sub_estop_ = this->create_subscription<std_msgs::msg::Bool>(
      "/usv/emergency_stop", 10,
      std::bind(&UsvController::estopCallback, this, std::placeholders::_1));

    // ── Publishers ────────────────────────────────────────────────────────
    pub_left_thrust_ = this->create_publisher<std_msgs::msg::Float64>(
      "/model/barco_EONSEA/joint/motor_izquierdo_joint/cmd_thrust", 10);

    pub_right_thrust_ = this->create_publisher<std_msgs::msg::Float64>(
      "/model/barco_EONSEA/joint/motor_derecho_joint/cmd_thrust", 10);

    pub_debug_ = this->create_publisher<geometry_msgs::msg::Twist>(
      "/usv/control_debug", 10);

    // ── Control loop at 20 Hz ─────────────────────────────────────────────
    prev_time_ = this->now();
    timer_ = this->create_wall_timer(
      std::chrono::milliseconds(50),
      std::bind(&UsvController::controlLoop, this));

    // ── Dynamic parameter callback ────────────────────────────────────────
    param_cb_handle_ = this->add_on_set_parameters_callback(
      std::bind(&UsvController::onParamChange, this, std::placeholders::_1));

    RCLCPP_INFO(this->get_logger(),
      "USV Controller ready — PID surge + yaw-rate, anti-windup, watchdog.");
  }

private:
  // ── PID state per axis ─────────────────────────────────────────────────
  struct PidState {
    double integral    = 0.0;
    double prev_error  = 0.0;
    double prev_deriv  = 0.0;  // filtered derivative
  };

  PidState pid_linear_;
  PidState pid_angular_;

  // ── Setpoints & measurements ──────────────────────────────────────────
  double target_linear_vel_  = 0.0;
  double target_angular_vel_ = 0.0;
  double current_linear_vel_ = 0.0;
  double current_angular_vel_= 0.0;

  // ── Safety flags ──────────────────────────────────────────────────────
  bool   emergency_stop_     = false;
  rclcpp::Time last_cmd_time_{0, 0, RCL_ROS_TIME};

  // ── Timing ────────────────────────────────────────────────────────────
  rclcpp::Time prev_time_;

  // ── ROS handles ───────────────────────────────────────────────────────
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr  sub_cmd_vel_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr    sub_odom_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr        sub_estop_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr        pub_left_thrust_;
  rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr        pub_right_thrust_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr     pub_debug_;
  rclcpp::TimerBase::SharedPtr                                timer_;
  rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr param_cb_handle_;

  // ── Callbacks ─────────────────────────────────────────────────────────
  void cmdVelCallback(const geometry_msgs::msg::Twist::SharedPtr msg)
  {
    target_linear_vel_  = msg->linear.x;
    target_angular_vel_ = msg->angular.z;
    last_cmd_time_      = this->now();
  }

  void odomCallback(const nav_msgs::msg::Odometry::SharedPtr msg)
  {
    current_linear_vel_  = msg->twist.twist.linear.x;
    current_angular_vel_ = msg->twist.twist.angular.z;
  }

  void estopCallback(const std_msgs::msg::Bool::SharedPtr msg)
  {
    emergency_stop_ = msg->data;
    if (emergency_stop_) {
      RCLCPP_WARN(this->get_logger(), "EMERGENCY STOP activated — thrusters cut.");
      publishThrust(0.0, 0.0);
    } else {
      RCLCPP_INFO(this->get_logger(), "Emergency stop cleared.");
    }
  }

  rcl_interfaces::msg::SetParametersResult
  onParamChange(const std::vector<rclcpp::Parameter> & /*params*/)
  {
    rcl_interfaces::msg::SetParametersResult result;
    result.successful = true;
    RCLCPP_INFO(this->get_logger(), "PID gains updated via dynamic reconfigure.");
    return result;
  }

  // ── Core PID computation (with anti-windup + derivative filter) ───────
  double computePid(PidState & state,
                    double error,
                    double dt,
                    double kp, double ki, double kd,
                    double integral_max,
                    double filter_coeff)
  {
    if (dt <= 0.0) return 0.0;

    // Proportional
    double p_term = kp * error;

    // Integral with clamping anti-windup
    state.integral += error * dt;
    state.integral  = std::clamp(state.integral, -integral_max, integral_max);
    double i_term   = ki * state.integral;

    // Derivative with first-order low-pass filter
    double raw_deriv   = (error - state.prev_error) / dt;
    double filt_deriv  = filter_coeff * state.prev_deriv
                       + (1.0 - filter_coeff) * raw_deriv;
    state.prev_deriv   = filt_deriv;
    double d_term      = kd * filt_deriv;

    state.prev_error = error;

    return p_term + i_term + d_term;
  }

  // ── Main 20 Hz control loop ───────────────────────────────────────────
  void controlLoop()
  {
    // Elapsed time
    rclcpp::Time now = this->now();
    double dt = (now - prev_time_).seconds();
    prev_time_ = now;

    // Safety: emergency stop
    if (emergency_stop_) {
      publishThrust(0.0, 0.0);
      return;
    }

    // Safety: watchdog — zero thrust if cmd_vel has gone stale
    double timeout = this->get_parameter("cmd_timeout_s").as_double();
    bool have_cmd  = (last_cmd_time_.nanoseconds() > 0);
    bool timed_out = have_cmd &&
                     ((now - last_cmd_time_).seconds() > timeout);

    if (!have_cmd || timed_out) {
      if (timed_out) {
        RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 2000,
          "cmd_vel timeout — holding zero thrust.");
      }
      // Reset integrators to avoid windup during silence
      pid_linear_.integral  = 0.0;
      pid_angular_.integral = 0.0;
      publishThrust(0.0, 0.0);
      return;
    }

    // Read gains
    double kp_l  = this->get_parameter("pid_linear.kp").as_double();
    double ki_l  = this->get_parameter("pid_linear.ki").as_double();
    double kd_l  = this->get_parameter("pid_linear.kd").as_double();
    double imax_l= this->get_parameter("pid_linear.integral_max").as_double();

    double kp_a  = this->get_parameter("pid_angular.kp").as_double();
    double ki_a  = this->get_parameter("pid_angular.ki").as_double();
    double kd_a  = this->get_parameter("pid_angular.kd").as_double();
    double imax_a= this->get_parameter("pid_angular.integral_max").as_double();

    double alpha = this->get_parameter("derivative_filter_coeff").as_double();

    // PID surge
    double error_linear  = target_linear_vel_  - current_linear_vel_;
    double control_linear = computePid(pid_linear_, error_linear, dt,
                                       kp_l, ki_l, kd_l, imax_l, alpha);

    // PID yaw-rate
    double error_angular  = target_angular_vel_ - current_angular_vel_;
    double control_angular = computePid(pid_angular_, error_angular, dt,
                                        kp_a, ki_a, kd_a, imax_a, alpha);

    // Differential mixing
    double left_thrust  = control_linear - control_angular;
    double right_thrust = control_linear + control_angular;

    // Clamp to thruster limits
    double t_max = this->get_parameter("thrust_max").as_double();
    double t_min = this->get_parameter("thrust_min").as_double();
    left_thrust  = std::clamp(left_thrust,  t_min, t_max);
    right_thrust = std::clamp(right_thrust, t_min, t_max);

    publishThrust(left_thrust, right_thrust);

    // Telemetry: reuse Twist to publish debug info cheaply
    // linear.x = error_surge, linear.y = control_surge
    // angular.x = error_yaw,  angular.y = control_yaw
    geometry_msgs::msg::Twist dbg;
    dbg.linear.x  = error_linear;
    dbg.linear.y  = control_linear;
    dbg.angular.x = error_angular;
    dbg.angular.y = control_angular;
    pub_debug_->publish(dbg);
  }

  // ── Helper ────────────────────────────────────────────────────────────
  void publishThrust(double left, double right)
  {
    std_msgs::msg::Float64 ml, mr;
    ml.data = left;
    mr.data = right;
    pub_left_thrust_->publish(ml);
    pub_right_thrust_->publish(mr);
  }
};

// ─────────────────────────────────────────────────────────────────────────────
int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<UsvController>());
  rclcpp::shutdown();
  return 0;
}