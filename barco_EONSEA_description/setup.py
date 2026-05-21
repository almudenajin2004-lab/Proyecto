import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'barco_EONSEA_description'

# Leer todas las subcarpetas de models automáticamente
models_data_files = []
for root, dirs, files in os.walk('models'):
    for file in files:
        # Añade cada archivo manteniendo la estructura de carpetas
        models_data_files.append((os.path.join('share', package_name, root), [os.path.join(root, file)]))

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*')),
        (os.path.join('share', package_name, 'meshes'), glob('meshes/*')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
    ] + models_data_files, 
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='almudena jin',
    maintainer_email='almjin04@gmail.com',
    description='The ' + package_name + ' package',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        ],
    },
)
