#!/usr/bin/env python3
"""Start the whole swarm stack in one process tree.

Everything below runs inside the container. The image's entrypoint already
sources /opt/ros/humble/setup.bash and the ros2_ws overlay, so the ROS-TCP
bridge can be launched directly here rather than in a second terminal.

    python3 launch_swarm.py                 # everything
    python3 launch_swarm.py --no-dashboard  # no Streamlit (run it on the host)
    python3 launch_swarm.py --no-bridge     # no Unity bridge (headless testing)
"""
import argparse
import importlib.util
import os
import signal
import subprocess
import sys
import time

ROOT = '/home/uav_project'

# real_detection.py (YOLOv8 on the live camera feed) is intentionally NOT
# launched. On a stylized/low-poly Unity scene YOLO mostly hallucinates ("kite",
# "frisbee", "sports ball"), which floods the pipeline. Unity's DroneSensor.cs is
# the detection source for the scenario. To use real CV instead, run this
# manually in the container:
#   python3 /home/uav_project/swarm/real_detection.py

CORE = [
    ('Drone Agent 1', [f'{ROOT}/swarm/drone_agent.py', '1'], 1),
    ('Drone Agent 2', [f'{ROOT}/swarm/drone_agent.py', '2'], 1),
    ('Drone Agent 3', [f'{ROOT}/swarm/drone_agent.py', '3'], 1),
    ('Swarm Coordinator', [f'{ROOT}/swarm/swarm_coordinator.py'], 2),
    ('Mission Planner', [f'{ROOT}/swarm/mission_planner.py'], 2),
    ('Swarm API (:8000)', [f'{ROOT}/swarm/swarm_api.py'], 3),
]

BRIDGE = ('Unity Bridge (:10000)', [
    'ros2', 'run', 'ros_tcp_endpoint', 'default_server_endpoint',
    '--ros-args', '-p', 'ROS_IP:=0.0.0.0',
], 2)

DASHBOARD = ('Dashboard (:8501)', [
    'streamlit', 'run', f'{ROOT}/dashboard.py',
    '--server.address', '0.0.0.0',
    '--server.port', '8501',
    '--server.headless', 'true',
], 2)


def build_plan(args):
    plan = list(CORE)
    if not args.no_bridge:
        plan.append(BRIDGE)
    if not args.no_dashboard:
        if importlib.util.find_spec('streamlit'):
            plan.append(DASHBOARD)
        else:
            print('  ! streamlit not installed in this image — skipping the '
                  'dashboard.\n    Rebuild the image, or run it on the host with '
                  '`streamlit run dashboard.py`.')
    return plan


class Swarm:
    def __init__(self, plan):
        self.plan = plan
        self.procs = [None] * len(plan)

    def spawn(self, i):
        name, cmd, _ = self.plan[i]
        # Python nodes are invoked through the running interpreter; ros2 and
        # streamlit are already on PATH.
        argv = [sys.executable] + cmd if cmd[0].endswith('.py') else cmd
        # Own process group so shutdown can take down any children too.
        return subprocess.Popen(argv, env=os.environ.copy(), start_new_session=True)

    def start(self):
        print('=' * 56)
        print('  UAV SWARM SYSTEM LAUNCHING')
        print('=' * 56)

        for i, (name, _, delay) in enumerate(self.plan):
            print(f'  starting {name} ...')
            self.procs[i] = self.spawn(i)
            time.sleep(delay)
            if self.procs[i].poll() is not None:
                print(f'  ! {name} exited immediately (code '
                      f'{self.procs[i].returncode})')
            else:
                print(f'  + {name} online')

        print('=' * 56)
        print('  ALL SYSTEMS ONLINE')
        print('  Dashboard : http://localhost:8501')
        print('  API       : http://localhost:8000/state')
        print('  Unity     : connect to the bridge on port 10000, then press Play')
        print('  Ctrl+C to shut everything down')
        print('=' * 56)

    def supervise(self):
        while True:
            for i, p in enumerate(self.procs):
                if p is not None and p.poll() is not None:
                    print(f'  ! {self.plan[i][0]} crashed — restarting')
                    self.procs[i] = self.spawn(i)
            time.sleep(5)

    def shutdown(self, *_):
        print('\nShutting down swarm ...')
        for p in self.procs:
            if p is None or p.poll() is not None:
                continue
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                p.terminate()

        # Give them a moment, then insist.
        deadline = time.time() + 5
        for p in self.procs:
            if p is None:
                continue
            try:
                p.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--no-bridge', action='store_true',
                    help='skip the Unity ROS-TCP bridge')
    ap.add_argument('--no-dashboard', action='store_true',
                    help='skip the Streamlit dashboard')
    args = ap.parse_args()

    swarm = Swarm(build_plan(args))
    signal.signal(signal.SIGINT, swarm.shutdown)
    signal.signal(signal.SIGTERM, swarm.shutdown)
    swarm.start()
    swarm.supervise()


if __name__ == '__main__':
    main()
