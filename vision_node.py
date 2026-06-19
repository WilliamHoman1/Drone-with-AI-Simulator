import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from ultralytics import YOLO
import cv2
import json
import numpy as np

class VisionNode(Node):
    def __init__(self, drone_id):
        super().__init__(f'vision_node_{drone_id}')
        self.drone_id = drone_id
        self.model = YOLO('yolov8n.pt')  # downloads automatically

        # Publisher — sends detections to mission planner
        self.detection_publisher = self.create_publisher(
            String,
            f'/drone_{drone_id}/detections',
            10
        )

        # Timer — runs detection every second
        self.timer = self.create_timer(1.0, self.detect)
        self.get_logger().info(f'Vision node {drone_id} online')

    def detect(self):
        # Simulate a camera frame (replace with real Gazebo camera later)
        frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        results = self.model(frame, verbose=False)

        detections = []
        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)]
                conf = float(box.conf)
                if conf > 0.3:
                    x, y, w, h = box.xywh[0].tolist()
                    detections.append({
                        'label': label,
                        'confidence': round(conf, 2),
                        'center': (int(x), int(y))
                    })

        if detections:
            msg = String()
            msg.data = json.dumps(detections)
            self.detection_publisher.publish(msg)
            self.get_logger().info(f'Drone {self.drone_id} detected: {[d["label"] for d in detections]}')
        else:
            self.get_logger().info(f'Drone {self.drone_id}: no detections')

def main():
    rclpy.init()
    vision = VisionNode(drone_id=1)
    try:
        rclpy.spin(vision)
    except KeyboardInterrupt:
        pass
    vision.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()