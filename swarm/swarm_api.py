from fastapi import FastAPI
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.node import Node
import json
import threading
import time
import uvicorn

app = FastAPI()

# Shared state
state = {
    'drones': {
        1: {'x': 10.0, 'y': 15.0, 'status': 'patrolling'},
        2: {'x': 30.0, 'y': 15.0, 'status': 'patrolling'},
        3: {'x': 50.0, 'y': 15.0, 'status': 'patrolling'}
    },
    'detections': [],
    'missions': [],
    'alerts': [],
    'scans': [],
    'active_targets': 0
}

def safe_json(node, msg, what):
    """Parse a ROS String payload, logging and skipping malformed messages.

    An exception raised inside a ROS callback propagates out of the executor and
    takes the whole node down — one bad frame from Unity would silently kill the
    dashboard bridge for the rest of the run.
    """
    try:
        return json.loads(msg.data)
    except (json.JSONDecodeError, TypeError) as e:
        node.get_logger().warn(f'Bad {what} payload ({e}): {msg.data[:120]!r}')
        return None


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
            # Unity is the authority on where each drone actually is.
            self.create_subscription(
                PoseStamped,
                f'/drone_{drone_id}/position',
                lambda msg, id=drone_id: self.position_cb(msg, id),
                10
            )
        self.create_subscription(
            String, '/swarm/status',
            self.status_cb, 10
        )
        self.create_subscription(
            String, '/swarm/alerts',
            self.alert_cb, 10
        )
        # Unity's TargetScan publishes here when a close-in scan classifies a
        # contact — the outcome of the mission, not just its dispatch.
        self.create_subscription(
            String, '/swarm/scan_result',
            self.scan_cb, 10
        )
        # Mission restart — clear the dashboard's history so it reflects the new
        # run rather than concatenating both.
        self.create_subscription(
            String, '/swarm/reset',
            self.reset_cb, 10
        )

    def detection_cb(self, msg, drone_id):
        dets = safe_json(self, msg, 'detection')
        if dets is None:
            return
        for d in dets:
            state['detections'].insert(0, {
                'drone': drone_id,
                'label': d['label'],
                'confidence': d['confidence'],
                'tier': d.get('tier', 'low'),
                'time': time.strftime('%H:%M:%S'),
                'x': round(state['drones'][drone_id]['x'], 1),
                'y': round(state['drones'][drone_id]['y'], 1)
            })
        state['detections'] = state['detections'][:20]

    def alert_cb(self, msg):
        alert = safe_json(self, msg, 'alert')
        if alert is None:
            return
        state['alerts'].insert(0, alert)
        state['alerts'] = state['alerts'][:20]

    def scan_cb(self, msg):
        scan = safe_json(self, msg, 'scan result')
        if scan is None:
            return
        state['scans'].insert(0, {
            'drone': scan['drone'],
            'label': scan['label'],
            'tier': scan.get('tier', 'low'),
            'result': scan['result'],
            'x': scan['x'],
            'y': scan['z'],
            'time': time.strftime('%H:%M:%S'),
        })
        state['scans'] = state['scans'][:20]
        state['missions'].insert(0, {
            'drone': scan['drone'],
            'mission': f"Scan complete — {scan['label']}: {scan['result']}",
            'time': time.strftime('%H:%M:%S'),
        })
        state['missions'] = state['missions'][:10]

    def reset_cb(self, msg):
        state['detections'].clear()
        state['missions'].clear()
        state['alerts'].clear()
        state['scans'].clear()
        state['active_targets'] = 0
        for drone in state['drones'].values():
            drone['status'] = 'patrolling'
        self.get_logger().info('Mission reset — cleared dashboard state')

    def position_cb(self, msg, drone_id):
        # ROS y on the dashboard map is Unity's z (ground plane).
        state['drones'][drone_id]['x'] = msg.pose.position.x
        state['drones'][drone_id]['y'] = msg.pose.position.z

    def mission_cb(self, msg, drone_id):
        waypoints = safe_json(self, msg, 'mission')
        if waypoints is None:
            return
        if waypoints:
            state['missions'].insert(0, {
                'drone': drone_id,
                'mission': f'Fly to {waypoints[0]}',
                'time': time.strftime('%H:%M:%S')
            })
        state['missions'] = state['missions'][:10]

    def status_cb(self, msg):
        data = safe_json(self, msg, 'status')
        if data is None:
            return
        state['active_targets'] = data.get('active_targets', 0)
        # The coordinator owns patrolling/investigating — mirror it rather than
        # inferring status from mission traffic.
        for drone_id, drone in data.get('drones', {}).items():
            key = int(drone_id)
            if key in state['drones'] and 'status' in drone:
                state['drones'][key]['status'] = drone['status']

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