# UAV Agent
To restart everything:
In VS Code terminal:
docker start uav_sim2
docker exec -it uav_sim2 bash
source /opt/ros/humble/setup.bash
cd /home/uav_project



And your Streamlit dashboard on your Mac terminal:
source venv/bin/activate
streamlit run dashboard.py


Next session goals:

Single launch script that starts all nodes at once
Wire real detections into the dashboard live
Start Gazebo 3D environment setup