# Proyecto EONSEA: Simulación y Teleoperación del USV

Esta rama contiene la simulación y el sistema de control teleoperado para el Vehículo de Superficie No Tripulado (USV) de **EONSEA**. El entorno está construido sobre **ROS 2 Jazzy** y **Gazebo Harmonic**, utilizando dinámicas basadas en el proyecto VRX.

## Requisitos Previos

Para ejecutar esta simulación, se tiene que ejercer sobre Ubuntu 24.04, y tener configurado tu entorno con **ROS 2 Jazzy** y **Gazebo Harmonic**.

`NOTA`: Si es la primera vez que configuras el entorno, abre una terminal y ejecuta los siguientes comandos para instalar todas las dependencias necesarias:

### ROS 2 | Gazebo |  Puente de comunicación

Asegúrate de tener el escritorio de ROS 2 y los paquetes de integración con Gazebo (incluyendo el `ros_gz_bridge` para conectar los topics):
Se instalará siguiendo los pasos de: https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html
Se asegura de instalar también el punte de comunicación:

```Bash

sudo apt install ros-jazzy-ros-gz
sudo apt install ros-jazzy-ros-gz-bridge
```


`NOTA`: Si se quiere facilitar la utilización de una nueva terminal se le configurar el entorno automáticamente:

```bash

echo "source /opt/ros/jazzy/setup.bash" >>.bashrc
```
Para comprobar que la instalación se ha realizado de forma correcta:
```bash

ros2 help
```
Debería salir una lista de paquetes instalados de ROS2.

## Instalación del repositorio

PASO 1 - Instalar dependencias específicas para VRX (requiere instalar Gazebo Harmonic y los siguientes paquetes adicionales):


```bash
# 1. Instalar herramientas necesarias
sudo apt update && sudo apt install -y curl gnupg

# 2. Descargar la clave del repositorio de Gazebo
sudo curl https://packages.osrfoundation.org/gazebo.key | sudo apt-key add -

# 3. Agregar el repositorio oficial a tus fuentes
sudo sh -c 'echo "deb http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" > /etc/apt/sources.list.d/gazebo-stable.list'

# 4. Actualizar la lista de paquetes
sudo apt update[11:41]sudo apt install python3-sdformat14
```
Nota: ROS 2 Jazzy es compatible únicamente con Gazebo Harmonic, y cuando instalas ros-jazzy-desktop este ya lo incluye por defecto.


Paso 2 — Crear el workspace y clonar VRX


```bash
mkdir -p ~/coral_ws
cd ~/coral_ws
# con "src" al final transformamos el repositorio directamente como carpeta src.
git clone https://github.com/ThaliaMorel/CORAL.git src
```
`NOTA`: Como este repositorio esta compuesto de varias ramas, al enlazar el ordenador con él, debemos realizar unos pasos para seleccionar la rama deseada:
1. Primero asegúrate de tener todas las referencias remotas:
```bash
git fetch
```
2. Seleccionamos la rama

```bash
git switch gazebo
```
`NOTA`: Aquí la rama deseada es `gazebo`, se cambia por la que nos interesa.

3. Para saber la rama situada:
```bash
git branch
```
Paso 3 — Compilar VRX

```bash
source /opt/ros/jazzy/setup.bash
cd ~/coral_ws
colcon build --symlink-install 
```
La compilación tarda varios minutos la primera vez.

Configurar el entorno de simulación
```bash
source ~/coral_ws/install/setup.bash
```

Paso 5 — Lanzar la simulación:

```Bash

ros2 launch simulation navegacion_eonsea.launch.py
```


#### Contenedor docker

Otra manera de poder ejercer el proyecto en otras versiones de Ubuntu o en Window es  estar dentro del contenedor Docker, el cual ya tiene instalados:
* ROS 2 Jazzy
* Gazebo Harmonic (`gz sim`)
* Paquetes de VRX (`vrx_gz`, `vrx_ros`)
* `ros_gz_bridge` (Para la comunicación entre ROS 2 y Gazebo)

## Estructura del Proyecto

A continuación, se detalla la organización de las carpetas más relevantes de este repositorio. El proyecto separa claramente los archivos 3D, la simulación pura en Gazebo y la integración con ROS 2:

```text
coral_ws/
    ├── build/
    ├── install/
    ├── log/
    └── src/                     # El enlace remoto de CORAL 
        ├── barco_EONSEA_description         # Módulo de descripción cinemática, visual y del entorno
        │   ├── barco_EONSEA_description     # Recursos internos y dependencias del paquete ament_python
        │   ├── config                       # Archivos de configuración de parámetros (formato YAML)
        │   ├── launch                       # Scripts de inicialización específicos del modelo y sensores
        │   ├── meshes                       # Modelos 3D para la visualización y cálculo de colisiones (STL/DAE)
        │   ├── models                       # Definición de modelos físicos de Gazebo (proyectil, texturas de agua)
        │   ├── package.xml                  # Manifiesto del paquete: metadatos y declaración de dependencias
        │   ├── resource                     # Archivos de indexación para el sistema de compilación ament
        │   ├── rviz                         # Perfiles de configuración para el entorno de visualización RViz2
        │   ├── setup.cfg                    # Directivas de configuración de empaquetado para Python
        │   ├── setup.py                     # Script de construcción, instalación y exportación de rutas del paquete
        │   ├── test                         # Directorio destinado a pruebas unitarias y de integración de software
        │   ├── urdf                         # Definición de la estructura, articulaciones, inercias y sensores (Xacro/URDF)
        │   └── worlds                       # Entornos de simulación configurados (e.g., sydney_regatta.sdf modificado)
        │
        ├── Changelog.md                     # Registro histórico de versiones, modificaciones y parches del código
        ├── docker                           # Entorno de despliegue y contenerización multiplataforma
        │   ├── docker-compose.yml           # Archivo de orquestación de servicios para despliegues complejos
        │   ├── Dockerfile.base              # Imagen base con las dependencias fundamentales del sistema operativo
        │   ├── Dockerfile.builder           # Imagen configurada para la compilación automatizada del espacio de trabajo
        │   ├── Dockerfile.devel             # Imagen orientada al desarrollo, depuración e integración continua
        │   ├── entrypoint-ros.sh            # Script de punto de entrada para la configuración del entorno de ROS 2
        │   ├── gz.repos                     # Definición de repositorios externos y dependencias de control de versiones
        │   └── README.md                    # Documentación específica para la construcción y uso del entorno Docker
        │
        ├── images                           # Recursos gráficos y diagramas para la documentación del repositorio
        │   └── sydney_regatta_gzsim.png
        ├── LICENSE                          # Términos legales y licencia de distribución del software (Open Source)
        ├── README.md                        # Documentación principal, arquitectura del proyecto y manual de usuario
        │
        ├── simulation                       # Módulo principal de simulación, control y ejecución de ella
        │   ├── CMakeLists.txt               # Directivas de compilación nativa de CMake para posibles nodos en C++
        │   ├── launch                       # Scripts generales de ejecución
        │   ├── package.xml                  # Manifiesto del paquete de control de simulación
        │   └── src                          # Código fuente (C/C++) reservado para algoritmos de control, trayectoria.
        │
        └── vrx_gz                           # Módulo de físicas avanzadas e hidrodinámica (Librerías Core de VRX)
            ├── CMakeLists.txt               # Directivas de compilación de las librerías dinámicas del motor físico
            ├── config                       # Archivos de configuración de parámetros heredados del motor base
            ├── hooks                        # Scripts de extensión para inyección de variables de entorno en Gazebo
            ├── launch                       # Scripts de lanzamiento originales del framework VRX (Deprecados en este proyecto)
            ├── models                       # Modelos originales de la competición (Ignorados por la configuración actual)
            ├── package.xml                  # Manifiesto de dependencias del motor físico
            ├── scripts                      # Herramientas de ajuste dinámico de variables climáticas (oleaje y viento)
            ├── src                          # Código fuente (C++) de los plugins de flotabilidad, hidrodinámica y clima
            └── worlds                       # Entornos originales del simulador VRX (Sustituidos por los entornos locales)

```

## Ejecución de la simulación

El sistema requiere **dos terminales** separadas: una para el entorno virtual y otra para el mando de control.

#### Terminal 1: Lanzar el Mundo, Barco y Controlador
Abre una terminal (si trabajas con el contenedor docker: nuestro workspace se llama `coral_ws` -> `ws`. También recuerda activarlo [docker compose up -d --build] y entrar [docker compose exec devel bash]), carga el entorno de ROS 2:
```bash
source /opt/ros/jazzy/setup.bash
source /coral_ws/install/setup.bash
```
Ejecuta con:
```Bash
ros2 launch simulation navegacion_eonsea.launch.py
```
#### Terminal 2: Iniciar el Teleoperador (Xbox / teclado)
`NOTA`: Si es la 1º vez en ejecutarlo :
```bash
sudo apt update
sudo apt install ros-jazzy-joy ros-jazzy-joy-teleop
apt-get update apt-get install ros-jazzy-teleop-twist-keyboard -y
```
Vuelve a cargar ROS 2 en la nueva terminal
```bash
source /opt/ros/jazzy/setup.bash
source ~/coral_ws/install/setup.bash
```
`Mando`:

```bash
ros2 launch simulation eonsea_joy.launch.py
```
`Teclado` (ijklm):

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```
#### Resetear el barco:

```bash
ros2 launch simulation eonsea_reset_launch.py
```
