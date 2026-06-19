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

        # Listen to all drone detections
        for drone_id in self.drones:
            self.create_subscription(
                String,
                f'/drone_{drone_id}/detections',
                lambda msg, id=drone_id: self.detection_callback(msg, id),
                10
            )

        # Publisher — sends missions to each drone
        self.mission_publishers = {
            id: self.create_publisher(String, f'/drone_{id}/mission', 10)
            for id in self.drones
        }

        self.get_logger().info('Mission planner online — waiting for detections')

    def detection_callback(self, msg, drone_id):
        detections = json.loads(msg.data)
        self.get_logger().info(f'Planner received detections from drone {drone_id}: {detections}')
        
        # Generate mission from LLM
        mission = self.plan_mission(detections, drone_id)
        
        # Send mission to drone
        mission_msg = String()
        mission_msg.data = json.dumps(mission)
        self.mission_publishers[drone_id].publish(mission_msg)

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
            # Fallback if LLM response can't be parsed
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