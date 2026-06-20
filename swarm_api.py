from fastapi import FastAPI
from std_msgs.msg import String
import rclpy
from rclpy.node import Node
import json
import threading
import time
from collections import deque
import uvicorn

app = FastAPI()

# Shared state
state = {
    'drones': {
        1: {'x': 0.0, 'y': 0.0, 'status': 'patrolling'},
        2: {'x': 20.0, 'y': 0.0, 'status': 'patrolling'},
        3: {'x': 10.0, 'y': 20.0, 'status': 'patrolling'}
    },
    'detections': [],
    'missions': [],
    'active_targets': 0
}

class StateListener(Node):
    def __init__(self):
        super().__init__('swarm_api_listener')
        for drone_id in range(1, 4):
            self.create_subscription(
                String,
                f'/drone_{drone_id}/detections',
                lambda msg, id=drone_id: self.detection_cb(msg, id),
                10
            )
            self.create_subscription(
                String,
                f'/drone_{drone_id}/mission',
                lambda msg, id=drone_id: self.mission_cb(msg, id),
                10
            )
        self.create_subscription(
            String, '/swarm/status',
            self.status_cb, 10
        )

    def detection_cb(self, msg, drone_id):
        dets = json.loads(msg.data)
        for d in dets:
            state['detections'].insert(0, {
                'drone': drone_id,
                'label': d['label'],
                'confidence': d['confidence'],
                'time': time.strftime('%H:%M:%S'),
                'x': round(state['drones'][drone_id]['x'], 1),
                'y': round(state['drones'][drone_id]['y'], 1)
            })
        state['detections'] = state['detections'][:20]

    def mission_cb(self, msg, drone_id):
        waypoints = json.loads(msg.data)
        if waypoints:
            state['drones'][drone_id]['x'] = waypoints[0][0]
            state['drones'][drone_id]['y'] = waypoints[0][1]
            state['drones'][drone_id]['status'] = 'investigating'
            state['missions'].insert(0, {
                'drone': drone_id,
                'mission': f'Fly to {waypoints[0]}',
                'time': time.strftime('%H:%M:%S')
            })
        state['missions'] = state['missions'][:10]

    def status_cb(self, msg):
        data = json.loads(msg.data)
        state['active_targets'] = data.get('active_targets', 0)

def ros_thread():
    rclpy.init()
    node = StateListener()
    rclpy.spin(node)

@app.get("/state")
def get_state():
    return state

@app.get("/health")
def health():
    return {"status": "online"}

if __name__ == '__main__':
    t = threading.Thread(target=ros_thread, daemon=True)
    t.start()
    time.sleep(2)
    uvicorn.run(app, host='0.0.0.0', port=8000)