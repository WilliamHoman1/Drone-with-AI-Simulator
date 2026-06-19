import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import json

class DroneAgent(Node):
    def __init__(self, drone_id):
        super().__init__(f'drone_agent_{drone_id}')
        self.drone_id = drone_id
        self.current_pos = (0, 0, 0)
        self.mission = []
        self.status = 'idle'

        # Publisher — broadcasts drone position
        self.pos_publisher = self.create_publisher(
            PoseStamped,
            f'/drone_{drone_id}/position',
            10
        )

        # Publisher — broadcasts detections
        self.detection_publisher = self.create_publisher(
            String,
            f'/drone_{drone_id}/detections',
            10
        )

        # Subscriber — listens for mission commands
        self.mission_subscriber = self.create_subscription(
            String,
            f'/drone_{drone_id}/mission',
            self.mission_callback,
            10
        )

        # Timer — runs every 0.5 seconds
        self.timer = self.create_timer(0.5, self.update)
        self.get_logger().info(f'Drone {drone_id} online')

    def mission_callback(self, msg):
        self.mission = json.loads(msg.data)
        self.status = 'active'
        self.get_logger().info(f'Drone {self.drone_id} received mission: {self.mission}')

    def update(self):
        # Publish current position
        pos_msg = PoseStamped()
        pos_msg.header.stamp = self.get_clock().now().to_msg()
        pos_msg.pose.position.x = float(self.current_pos[0])
        pos_msg.pose.position.y = float(self.current_pos[1])
        pos_msg.pose.position.z = float(self.current_pos[2])
        self.pos_publisher.publish(pos_msg)

        # If we have a mission, move toward next waypoint
        if self.mission and self.status == 'active':
            next_wp = self.mission[0]
            self.current_pos = (
                self.current_pos[0] + (next_wp[0] - self.current_pos[0]) * 0.1,
                self.current_pos[1] + (next_wp[1] - self.current_pos[1]) * 0.1,
                10.0
            )
            # Check if we reached the waypoint
            dist = abs(self.current_pos[0] - next_wp[0]) + abs(self.current_pos[1] - next_wp[1])
            if dist < 0.5:
                self.get_logger().info(f'Drone {self.drone_id} reached waypoint {next_wp}')
                self.mission.pop(0)

def main():
    rclpy.init()
    drone = DroneAgent(drone_id=1)
    try:
        rclpy.spin(drone)
    except KeyboardInterrupt:
        pass
    drone.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()