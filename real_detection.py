import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from ultralytics import YOLO
import cv2
import json
import numpy as np
import urllib.request
import os

class RealVisionNode(Node):
    def __init__(self, drone_id):
        super().__init__(f'real_vision_node_{drone_id}')
        self.drone_id = drone_id
        self.model = YOLO('yolov8n.pt')

        # Download a sample aerial image to detect from
        self.image_path = '/home/uav_project/aerial_scene.jpg'
        if not os.path.exists(self.image_path):
            self.get_logger().info('Downloading sample aerial image...')
            urllib.request.urlretrieve(
                'https://ultralytics.com/images/bus.jpg',
                self.image_path
            )
            self.get_logger().info('Image downloaded')

        # Publisher
        self.detection_publisher = self.create_publisher(
            String,
            f'/drone_{drone_id}/detections',
            10
        )

        # Timer — run detection every 3 seconds
        self.timer = self.create_timer(3.0, self.detect)
        self.get_logger().info(f'Real vision node {drone_id} online')

    def detect(self):
        # Load and run detection on real image
        results = self.model(self.image_path, verbose=False)

        detections = []
        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)]
                conf = float(box.conf)
                if conf > 0.4:
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
            self.get_logger().info(
                f'Drone {self.drone_id} detected: '
                f'{[(d["label"], d["confidence"]) for d in detections]}'
            )

            # Save annotated image so you can see what was detected
            annotated = results[0].plot()
            cv2.imwrite('/home/uav_project/detection_result.jpg', annotated)
            self.get_logger().info('Saved annotated image to detection_result.jpg')
        else:
            self.get_logger().info(f'Drone {self.drone_id}: no detections')

def main():
    rclpy.init()
    vision = RealVisionNode(drone_id=1)
    try:
        rclpy.spin(vision)
    except KeyboardInterrupt:
        pass
    vision.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
    