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

**0. Build the container image (once, or whenever `Dockerfile`/`docker/requirements.txt` change):**
```bash
docker build -t uav_swarm:latest .
```
This installs ROS 2 Humble, builds the `ros_tcp_endpoint` package, and installs the Python
dependencies (`docker/requirements.txt`) — everything needed to run the swarm, from a clean
Dockerfile instead of a hand-configured container. Mac-side dependencies for the dashboard and
`sim/sim_3d.py` live in the root `requirements.txt` (`pip install -r requirements.txt` inside `venv/`).

**1. Start the container, with this repo bind-mounted at `/home/uav_project`:**
```bash
docker run -it --rm \
  -v "$(pwd):/home/uav_project" \
  -p 8000:8000 -p 10000:10000 \
  -e ANTHROPIC_API_KEY \
  --name uav_swarm \
  uav_swarm:latest bash
```
Editing files on your Mac immediately shows up inside the container — no rebuild needed for
Python changes, only for new apt/pip dependencies.

**2. Launch all swarm nodes:**
```bash
python3 launch_swarm.py
```

**3. Start the ROS-Unity bridge:**
```bash
# In a second terminal: docker exec -it uav_swarm bash
cd ros2_ws
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

```
Drone_Simulator/
├── swarm/              # ROS 2 nodes (run inside the Docker container)
│   ├── drone_agent.py       # per-drone agent node
│   ├── swarm_coordinator.py # distributed task handoff / coordination
│   ├── real_detection.py    # live YOLOv8 detection node (camera feed)
│   ├── vision_node.py       # detection node variant
│   ├── mission_planner.py   # Claude-powered natural language -> flight plan
│   ├── ros_bridge.py        # ROS <-> external state bridge
│   ├── swarm_api.py         # FastAPI service exposing live swarm state
│   └── swarm_launcher.py    # in-container node launcher
├── sim/                 # standalone 3D simulation (no ROS/Unity required)
│   ├── sim_3d.py
│   └── drone_world.sdf
├── models/               # YOLO model weights (gitignored, auto-downloaded)
├── assets/               # demo images
├── launch_swarm.py       # single entrypoint that starts all swarm/ nodes
├── dashboard.py          # Streamlit live dashboard (run from your Mac)
├── Dockerfile             # reproducible ROS 2 + YOLO + swarm container
├── docker/requirements.txt # Python deps installed inside the container
├── requirements.txt       # Python deps for the Mac-side venv (dashboard, sim/)
├── UAV-Swarm-Swim/       # Unity project (own git repo/remote)
├── ros2_ws/              # ROS 2 workspace (colcon build)
└── venv/                 # Python virtualenv (gitignored)
```

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