import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
import anthropic
import json
import math
import os

# Commander-mode mission planner.
#
# Autonomous target handling lives entirely in swarm_coordinator.py — this node
# used to ALSO subscribe to /drone_*/detections and publish missions, which
# fought the coordinator for control of the same topic and sent every drone the
# same fallback waypoints. It now only handles explicit operator orders from
# Unity's Commander mode (/commander/order), optionally using Claude to turn a
# free-text order into waypoints.

MODEL = 'claude-opus-5'


class MissionPlanner(Node):
    def __init__(self):
        super().__init__('mission_planner')

        key = os.getenv('ANTHROPIC_API_KEY')
        self.client = anthropic.Anthropic(api_key=key) if key else None
        if self.client is None:
            self.get_logger().warn('ANTHROPIC_API_KEY not set — orders will be routed without LLM planning')

        # Sector centres of the 60 x 30 search area (see SearchPattern.cs).
        self.drone_pos = {1: (10.0, 15.0), 2: (30.0, 15.0), 3: (50.0, 15.0)}

        for drone_id in (1, 2, 3):
            self.create_subscription(
                PoseStamped, f'/drone_{drone_id}/position',
                lambda msg, i=drone_id: self.position_cb(msg, i), 10
            )

        self.mission_publishers = {
            i: self.create_publisher(String, f'/drone_{i}/mission', 10)
            for i in (1, 2, 3)
        }
        self.create_subscription(String, '/commander/order', self.order_cb, 10)
        self.response_publisher = self.create_publisher(String, '/commander/response', 10)

        self.get_logger().info('Mission planner online — waiting for commander orders')

    def position_cb(self, msg, drone_id):
        self.drone_pos[drone_id] = (msg.pose.position.x, msg.pose.position.z)

    def closest_drone(self, x, z):
        return min(self.drone_pos,
                   key=lambda i: math.hypot(self.drone_pos[i][0] - x, self.drone_pos[i][1] - z))

    def order_cb(self, msg):
        try:
            order = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Unparseable commander order: {msg.data!r}')
            return

        x, z = float(order['x']), float(order['z'])
        drone_id = self.closest_drone(x, z)
        waypoints = self.plan(order, drone_id, x, z)

        self.mission_publishers[drone_id].publish(String(data=json.dumps(waypoints)))
        self.response_publisher.publish(
            String(data=f'Drone {drone_id} dispatched to ({x:.1f}, {z:.1f})')
        )
        self.get_logger().info(f'Commander order → Drone {drone_id} via {waypoints}')

    def plan(self, order, drone_id, x, z):
        """Turn an order into a waypoint list. Uses Claude for free-text orders,
        otherwise just flies straight to the point."""
        instruction = order.get('instruction')
        if not instruction or self.client is None:
            return [[round(x, 1), round(z, 1)]]

        prompt = (
            f"Drone {drone_id} is at {self.drone_pos[drone_id]}. Operator order: "
            f"\"{instruction}\" near ({x:.0f}, {z:.0f}). Return ONLY a JSON array of "
            f"[x, z] waypoints that carries out the order, ending at the target. "
            f"The search area is x 0-60, z 0-30. Example: [[10,10],[25,25]]"
        )
        try:
            resp = self.client.messages.create(
                model=MODEL, max_tokens=300,
                output_config={'effort': 'low'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            text = next(b.text for b in resp.content if b.type == 'text')
            return json.loads(text)
        except Exception as e:
            self.get_logger().warn(f'LLM planning failed ({e}) — flying direct')
            return [[round(x, 1), round(z, 1)]]


def main():
    rclpy.init()
    node = MissionPlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
