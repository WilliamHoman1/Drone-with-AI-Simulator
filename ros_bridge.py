import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import threading
from collections import deque
import time

# Shared state between ROS and Streamlit
swarm_state = {
    'drones': {
        1: {'x': 0.0, 'y': 0.0, 'status': 'patrolling'},
        2: {'x': 20.0, 'y': 0.0, 'status': 'patrolling'},
        3: {'x': 10.0, 'y': 20.0, 'status': 'patrolling'}
    },
    'detections': deque(maxlen=20),
    'missions': deque(maxlen=10),
    'active_targets': 0
}

class ROSBridge(Node):
    def __init__(self):
        super().__init__('ros_bridge')

        # Subscribe to all drone detections
        for drone_id in range(1, 4):
            self.create_subscription(
                String,
                f'/drone_{drone_id}/detections',
                lambda msg, id=drone_id: self.detection_callback(msg, id),
                10
            )
            self.create_subscription(
                String,
                f'/drone_{drone_id}/mission',
                lambda msg, id=drone_id: self.mission_callback(msg, id),
                10
            )

        # Subscribe to swarm status
        self.create_subscription(
            String,
            '/swarm/status',
            self.status_callback,
            10
        )

        self.get_logger().info('ROS bridge online')

    def detection_callback(self, msg, drone_id):
        detections = json.loads(msg.data)
        for det in detections:
            swarm_state['detections'].appendleft({
                'drone': drone_id,
                'label': det['label'],
                'confidence': det['confidence'],
                'time': time.strftime('%H:%M:%S'),
                'x': round(swarm_state['drones'][drone_id]['x'], 1),
                'y': round(swarm_state['drones'][drone_id]['y'], 1)
            })

    def mission_callback(self, msg, drone_id):
        waypoints = json.loads(msg.data)
        swarm_state['missions'].appendleft({
            'drone': drone_id,
            'mission': f'Fly to {waypoints[0] if waypoints else "unknown"}',
            'time': time.strftime('%H:%M:%S')
        })
        # Update drone position target
        if waypoints:
            swarm_state['drones'][drone_id]['x'] = waypoints[0][0]
            swarm_state['drones'][drone_id]['y'] = waypoints[0][1]
            swarm_state['drones'][drone_id]['status'] = 'investigating'

    def status_callback(self, msg):
        data = json.loads(msg.data)
        swarm_state['active_targets'] = data.get('active_targets', 0)
        for drone_id, state in data.get('drones', {}).items():
            drone_id = int(drone_id)
            if drone_id in swarm_state['drones']:
                swarm_state['drones'][drone_id]['status'] = state.get('status', 'patrolling')

def start_ros_bridge():
    rclpy.init()
    bridge = ROSBridge()
    rclpy.spin(bridge)
    bridge.destroy_node()
    rclpy.shutdown()

# Start ROS bridge in background thread
def init_bridge():
    thread = threading.Thread(target=start_ros_bridge, daemon=True)
    thread.start()
    return swarm_state