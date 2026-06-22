import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import anthropic
import json
import os

class MissionPlanner(Node):
    def __init__(self):
        super().__init__('mission_planner')
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.drones = {1: 'idle', 2: 'idle', 3: 'idle'}
        self.drone_states = {
            1: {'x': 0.0, 'y': 0.0},
            2: {'x': 20.0, 'y': 0.0},
            3: {'x': 10.0, 'y': 20.0}
        }

        # Listen to all drone detections
        for drone_id in self.drones:
            self.create_subscription(
                String,
                f'/drone_{drone_id}/detections',
                lambda msg, id=drone_id: self.detection_callback(msg, id),
                10
            )
            # Track drone positions
            self.create_subscription(
                String,
                f'/drone_{drone_id}/position_update',
                lambda msg, id=drone_id: self.position_callback(msg, id),
                10
            )

        # Publisher — sends missions to each drone
        self.mission_publishers = {
            id: self.create_publisher(String, f'/drone_{id}/mission', 10)
            for id in self.drones
        }

        # Commander order subscription
        self.create_subscription(
            String,
            '/commander/order',
            self.commander_callback,
            10
        )

        self.commander_publisher = self.create_publisher(
            String, '/commander/response', 10
        )

        self.get_logger().info('Mission planner online — waiting for detections')

    def position_callback(self, msg, drone_id):
        try:
            data = json.loads(msg.data)
            self.drone_states[drone_id]['x'] = data['x']
            self.drone_states[drone_id]['y'] = data['y']
        except:
            pass

    def detection_callback(self, msg, drone_id):
        detections = json.loads(msg.data)
        self.get_logger().info(f'Planner received detections from drone {drone_id}: {detections}')
        mission = self.plan_mission(detections, drone_id)
        mission_msg = String()
        mission_msg.data = json.dumps(mission)
        self.mission_publishers[drone_id].publish(mission_msg)

    def commander_callback(self, msg):
        try:
            order = json.loads(msg.data)
            x, z = float(order['x']), float(order['z'])

            # Find closest available drone
            best_drone = min(
                self.drone_states.keys(),
                key=lambda id: abs(self.drone_states[id]['x'] - x) + abs(self.drone_states[id]['y'] - z)
            )

            # Send mission to closest drone
            mission = [[round(x, 1), round(z, 1)]]
            mission_msg = String()
            mission_msg.data = json.dumps(mission)
            self.mission_publishers[best_drone].publish(mission_msg)

            # Respond with assignment
            response = String()
            response.data = f"Drone {best_drone} dispatched to ({x:.1f}, {z:.1f})"
            self.commander_publisher.publish(response)

            self.get_logger().info(f"Commander order: Drone {best_drone} → ({x:.1f}, {z:.1f})")
        except Exception as e:
            self.get_logger().error(f"Commander callback error: {e}")

    def plan_mission(self, detections, drone_id):
        prompt = f"""
        Drone {drone_id} detected: {json.dumps(detections)}
        Generate a patrol mission as a JSON array of [x, y] waypoints.
        Prioritize investigating high confidence detections.
        Return ONLY a JSON array like [[x1,y1],[x2,y2],[x3,y3]].
        Coordinates must be between 0 and 50.
        """
        response = self.client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        try:
            waypoints = json.loads(response.content[0].text)
            self.get_logger().info(f'LLM planned mission for drone {drone_id}: {waypoints}')
            return waypoints
        except:
            return [[10, 10], [20, 20], [30, 30]]

def main():
    rclpy.init()
    planner = MissionPlanner()
    try:
        rclpy.spin(planner)
    except KeyboardInterrupt:
        pass
    planner.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()