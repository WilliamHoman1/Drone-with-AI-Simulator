import subprocess
import time
import os
import signal
import sys

# All nodes to launch in order
NODES = [
    {
        'name': 'Drone Agent 1',
        'cmd': 'python3 /home/uav_project/swarm/drone_agent.py',
        'delay': 1
    },
    {
        'name': 'Drone Agent 2',
        'cmd': 'python3 /home/uav_project/swarm/drone_agent.py 2',
        'delay': 1
    },
    {
        'name': 'Drone Agent 3',
        'cmd': 'python3 /home/uav_project/swarm/drone_agent.py 3',
        'delay': 1
    },
    {
        'name': 'Swarm Coordinator',
        'cmd': 'python3 /home/uav_project/swarm/swarm_coordinator.py',
        'delay': 2
    },
    {
        'name': 'Vision Node',
        'cmd': 'python3 /home/uav_project/swarm/real_detection.py',
        'delay': 2
    },
    {
        'name': 'Mission Planner',
        'cmd': 'python3 /home/uav_project/swarm/mission_planner.py',
        'delay': 2
    }
]

processes = []

def shutdown(sig, frame):
    print('\nShutting down swarm...')
    for p in processes:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

def launch():
    print('='*50)
    print('  UAV SWARM SYSTEM LAUNCHING')
    print('='*50)

    env = os.environ.copy()

    for node in NODES:
        print(f'Starting {node["name"]}...')
        p = subprocess.Popen(
            node['cmd'].split(),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(p)
        time.sleep(node['delay'])
        
        if p.poll() is not None:
            print(f'ERROR: {node["name"]} failed to start')
            out, err = p.communicate()
            print(err.decode())
        else:
            print(f'{node["name"]} online')

    print('='*50)
    print('  ALL SYSTEMS ONLINE')
    print('  Press Ctrl+C to shutdown')
    print('='*50)

    # Keep running and monitor processes
    while True:
        for i, p in enumerate(processes):
            if p.poll() is not None:
                print(f'WARNING: {NODES[i]["name"]} crashed — restarting...')
                new_p = subprocess.Popen(
                    NODES[i]['cmd'].split(),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                processes[i] = new_p
        time.sleep(5)

if __name__ == '__main__':
    launch()