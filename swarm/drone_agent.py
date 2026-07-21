import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json


class DroneAgent(Node):
    """Lightweight ROS-side presence for a drone: logs missions it's assigned.

    Unity (DroneController.cs) is the authoritative source for this drone's
    actual position and movement — it publishes PoseStamped on
    /drone_{id}/position itself. This node used to run its own independent
    position simulation on the same topic, which raced Unity's real
    publisher and fed swarm_coordinator.py stale/conflicting data.
    """

    def __init__(self, drone_id):
        super().__init__(f'drone_agent_{drone_id}')
        self.drone_id = drone_id

        self.mission_subscriber = self.create_subscription(
            String,
            f'/drone_{drone_id}/mission',
            self.mission_callback,
            10
        )

        self.get_logger().info(f'Drone {drone_id} online')

    def mission_callback(self, msg):
        mission = json.loads(msg.data)
        self.get_logger().info(f'Drone {self.drone_id} received mission: {mission}')


def main():
    import sys
    drone_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    rclpy.init()
    drone = DroneAgent(drone_id=drone_id)
    try:
        rclpy.spin(drone)
    except KeyboardInterrupt:
        pass
    drone.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
