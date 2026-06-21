# Autonomous Multi-Agent Drone Swarm Simulation

A fully autonomous drone swarm system built with ROS 2, Python, YOLOv8, the Anthropic API, and Unity. Three autonomous drone agents coordinate in real time to patrol a 3D environment, detect objects using computer vision, and dynamically reassign mission objectives using a distributed swarm coordination algorithm.

![Swarm Dashboard](detection_result.jpg)

## Demo

> 3 autonomous drones • Real-time object detection • LLM mission planning • Live 3D visualization

---

## Features

- **Multi-agent swarm** — 3 ROS 2 drone nodes operating autonomously in parallel
- **A* pathfinding** — optimal obstacle-avoiding navigation between waypoints
- **YOLOv8 object detection** — real-time computer vision with confidence-based target prioritization
- **LLM mission planner** — Claude (Anthropic API) converts natural language objectives into structured flight plans
- **Distributed coordination** — drones communicate detections and hand off targets to the closest available agent
- **Live dashboard** — Streamlit web UI showing drone positions, detection log, and mission log in real time
- **FastAPI bridge** — exposes live swarm state as a REST API
- **Unity 3D visualization** — real drone movement in a 3D environment connected to live ROS 2 data
- **Single launch script** — one command starts the entire system

---

## Defense Applications

- ISR (Intelligence, Surveillance, Reconnaissance) patrol automation
- Perimeter monitoring with autonomous threat detection
- Logistics resupply route optimization
- Multi-vehicle coordination for contested environments

---

## Architecture

---

## Tech Stack

| Layer | Technology |
|---|---|
| Robotics middleware | ROS 2 Humble |
| Simulation | Docker (Ubuntu 22.04 ARM64) |
| Object detection | YOLOv8 (Ultralytics) |
| Mission planning | Anthropic API (Claude) |
| Pathfinding | A* search algorithm |
| API bridge | FastAPI + Uvicorn |
| Dashboard | Streamlit + Plotly |
| 3D visualization | Unity 6.3 URP + C# |
| Language | Python 3.13, C# |
| Container | Docker |

---

## Getting Started

### Prerequisites
- Docker Desktop
- Python 3.x
- Unity 6.3 LTS
- Anthropic API key

### Run the swarm

**1. Start the Docker container:**
```bash
docker start uav_sim6
docker exec -it uav_sim6 bash
source /opt/ros/humble/setup.bash
cd /home/uav_project
export ANTHROPIC_API_KEY=your_key_here
```

**2. Launch all swarm nodes:**
```bash
python3 launch_swarm.py
```

**3. Start the ROS-Unity bridge:**
```bash
# In a second container terminal
source /opt/ros/humble/setup.bash
cd /home/uav_project/ros2_ws
source install/setup.bash
ros2 run ros_tcp_endpoint default_server_endpoint --ros-args -p ROS_IP:=0.0.0.0
```

**4. Start the dashboard:**
```bash
# On your Mac
source venv/bin/activate
streamlit run dashboard.py
```

**5. Open Unity and hit Play**

---

## Project Structure

---

## Roadmap

- [x] Multi-agent ROS 2 swarm
- [x] A* pathfinding and task prioritization
- [x] YOLOv8 real-time object detection
- [x] LLM mission planner
- [x] Distributed swarm coordination
- [x] Live Streamlit dashboard
- [x] Unity 3D visualization
- [ ] Reinforcement learning for adaptive patrol routes
- [ ] Gazebo physics integration
- [ ] Multi-drone camera feeds in Unity
- [ ] Threat classification and escalation logic

---

## Author

William Homan — CS Student @ University of Georgia | AI/Automation Engineer Intern Currently


Built to demonstrate autonomous systems, multi-agent AI coordination, and defense-relevant simulation — targeting roles at companies like Anduril, Shield AI, and L3Harris.