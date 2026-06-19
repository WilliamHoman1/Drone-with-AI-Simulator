import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import math
import time

class SwarmCoordinator(Node):
    def __init__(self):
        super().__init__('swarm_coordinator')
        
        self.num_drones = 3
        
        # Track each drone's position and status
        self.drone_states = {
            1: {'x': 0, 'y': 0, 'status': 'patrolling', 'current_target': None},
            2: {'x': 20, 'y': 0, 'status': 'patrolling', 'current_target': None},
            3: {'x': 10, 'y': 20, 'status': 'patrolling', 'current_target': None}
        }

        self.active_targets = {}  # target_id: {x, y, label, assigned_drone}
        self.target_counter = 0

        # Subscribe to each drone's detections and position
        for drone_id in range(1, self.num_drones + 1):
            self.create_subscription(
                String,
                f'/drone_{drone_id}/detections',
                lambda msg, id=drone_id: self.detection_callback(msg, id),
                10
            )
            self.create_subscription(
                String,
                f'/drone_{drone_id}/position_update',
                lambda msg, id=drone_id: self.position_callback(msg, id),
                10
            )

        # Publishers for drone missions
        self.mission_publishers = {
            id: self.create_publisher(String, f'/drone_{id}/mission', 10)
            for id in range(1, self.num_drones + 1)
        }

        # Publisher for swarm status
        self.swarm_status_publisher = self.create_publisher(
            String, '/swarm/status', 10
        )

        self.timer = self.create_timer(2.0, self.coordinate)
        self.get_logger().info('Swarm coordinator online')

    def position_callback(self, msg, drone_id):
        data = json.loads(msg.data)
        self.drone_states[drone_id]['x'] = data['x']
        self.drone_states[drone_id]['y'] = data['y']

    def detection_callback(self, msg, drone_id):
        detections = json.loads(msg.data)
        
        for det in detections:
            self.target_counter += 1
            target_id = self.target_counter
            
            # Estimate target position from detecting drone's position
            drone = self.drone_states[drone_id]
            target = {
                'x': drone['x'] + det['center'][0] / 64,
                'y': drone['y'] + det['center'][1] / 64,
                'label': det['label'],
                'confidence': det['confidence'],
                'detected_by': drone_id,
                'assigned_drone': None,
                'time': time.time()
            }
            
            self.active_targets[target_id] = target
            self.get_logger().info(
                f'New target #{target_id}: {det["label"]} '
                f'(conf: {det["confidence"]}) detected by drone {drone_id}'
            )
            
            # Find best drone to investigate
            self.assign_target(target_id)

    def distance(self, drone_id, target):
        drone = self.drone_states[drone_id]
        return math.sqrt(
            (drone['x'] - target['x'])**2 + 
            (drone['y'] - target['y'])**2
        )

    def assign_target(self, target_id):
        target = self.active_targets[target_id]
        
        # Find closest available drone
        best_drone = None
        best_dist = float('inf')
        
        for drone_id, state in self.drone_states.items():
            if state['status'] == 'patrolling':
                dist = self.distance(drone_id, target)
                if dist < best_dist:
                    best_dist = dist
                    best_drone = drone_id

        if best_drone:
            # Assign target to best drone
            target['assigned_drone'] = best_drone
            self.drone_states[best_drone]['status'] = 'investigating'
            self.drone_states[best_drone]['current_target'] = target_id

            # Send mission to that drone
            mission = [[round(target['x'], 1), round(target['y'], 1)]]
            msg = String()
            msg.data = json.dumps(mission)
            self.mission_publishers[best_drone].publish(msg)

            self.get_logger().info(
                f'Drone {best_drone} assigned to investigate '
                f'{target["label"]} at ({target["x"]:.1f}, {target["y"]:.1f})'
            )
        else:
            self.get_logger().info(f'No available drones for target #{target_id} — queued')

    def coordinate(self):
        # Check if any investigating drones have reached their target
        for drone_id, state in self.drone_states.items():
            if state['status'] == 'investigating' and state['current_target']:
                target_id = state['current_target']
                if target_id in self.active_targets:
                    target = self.active_targets[target_id]
                    dist = self.distance(drone_id, target)
                    
                    if dist < 2.0:
                        self.get_logger().info(
                            f'Drone {drone_id} reached target #{target_id} '
                            f'({target["label"]}) — returning to patrol'
                        )
                        state['status'] = 'patrolling'
                        state['current_target'] = None
                        del self.active_targets[target_id]

        # Publish swarm status
        status = {
            'drones': self.drone_states,
            'active_targets': len(self.active_targets)
        }
        msg = String()
        msg.data = json.dumps(status, default=str)
        self.swarm_status_publisher.publish(msg)

def main():
    rclpy.init()
    coordinator = SwarmCoordinator()
    try:
        rclpy.spin(coordinator)
    except KeyboardInterrupt:
        pass
    coordinator.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()