# Reproduces the uav_sim6 environment: ROS 2 Humble + rclpy swarm nodes +
# YOLOv8 detection + the Anthropic-powered mission planner + the FastAPI bridge.
# Unity talks to this container over the ROS-TCP-Endpoint (port 10000) and the
# dashboard talks to it over the FastAPI bridge (port 8000).
FROM ros:humble

ENV ROS_DISTRO=humble \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-colcon-common-extensions \
        ros-humble-vision-msgs \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/uav_project

# Build the ROS-TCP-Endpoint package once at image build time so a fresh
# container doesn't need a manual `colcon build` before it can bridge to Unity.
# Must happen before the pip install below: newer setuptools/packaging pulled in
# by the Python deps breaks colcon's setup.py invocation for this package.
COPY ros2_ws/src ros2_ws/src
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    cd ros2_ws && colcon build --packages-select ros_tcp_endpoint"

COPY docker/requirements.txt /tmp/requirements.txt
# CPU-only torch: this runs in Docker Desktop's Linux VM with no GPU passthrough,
# so the default (CUDA) torch wheel just drags in several GB of unused nvidia-* packages.
RUN pip3 install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements.txt

COPY docker/entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

EXPOSE 8000 10000

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]
