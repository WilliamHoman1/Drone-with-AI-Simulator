import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import threading

class SwarmLauncher(Node):
    def __init__(self):
        super().__init__('swarm_launcher')
        
        self.num_drones = 3
        
        # Track each drone's status and position
        self.drone_status = {1: 'idle', 2: 'idle', 3: 'idle'}
        self.drone_positions = {
            1: (0, 0, 0),
            2: (5, 0, 0),
            3: (10, 0, 0)
        }

        # Subscribe to each drone's position
        for drone_id in range(1, self.num_drones + 1):
            self.create_subscription(
                String,
                f'/drone_{drone_id}/status',
                lambda msg, id=drone_id: self.status_callback(msg, id),
                10
            )

        # Publisher for each drone's mission
        self.mission_publishers = {
            id: self.create_publisher(String, f'/drone_{id}/mission', 10)
            for id in range(1, self.num_drones + 1)
        }

        # Timer — assigns patrol zones every 10 seconds
        self.timer = self.create_timer(10.0, self.assign_patrol_zones)
        self.get_logger().info(f'Swarm launcher online — managing {self.num_drones} drones')

    def status_callback(self, msg, drone_id):
        self.drone_status[drone_id] = msg.data
        self.get_logger().info(f'Drone {drone_id} status: {msg.data}')

    def assign_patrol_zones(self):
        # Divide the map into zones for each drone
        zones = {
            1: [[0, 0], [10, 0], [10, 10], [0, 10]],   # northwest
            2: [[20, 0], [30, 0], [30, 10], [20, 10]],  # northeast  
            3: [[10, 20], [20, 20], [20, 30], [10, 30]]  # south
        }

        for drone_id, waypoints in zones.items():
            if self.drone_status[drone_id] == 'idle':
                msg = String()
                msg.data = json.dumps(waypoints)
                self.mission_publishers[drone_id].publish(msg)
                self.drone_status[drone_id] = 'active'
                self.get_logger().info(f'Assigned zone to drone {drone_id}: {waypoints}')

def main():
    rclpy.init()
    launcher = SwarmLauncher()
    try:
        rclpy.spin(launcher)
    except KeyboardInterrupt:
        pass
    launcher.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()