import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import base64
import json

import cv2
import numpy as np
from ultralytics import YOLO

CONFIDENCE_THRESHOLD = 0.4
DRONE_IDS = (1, 2, 3)


class RealVisionNode(Node):
    """Runs YOLO on each drone's live camera_frame topic (published by Unity)
    and republishes detections with real, in-frame pixel coordinates."""

    def __init__(self):
        super().__init__('real_vision_node')
        self.model = YOLO('models/yolov8n.pt')

        self.detection_publishers = {}
        for drone_id in DRONE_IDS:
            self.detection_publishers[drone_id] = self.create_publisher(
                String, f'/drone_{drone_id}/detections', 10
            )
            self.create_subscription(
                String,
                f'/drone_{drone_id}/camera_frame',
                lambda msg, id=drone_id: self.on_frame(msg, id),
                10
            )

        self.get_logger().info('Real vision node online — waiting for camera frames')

    def on_frame(self, msg, drone_id):
        try:
            jpeg_bytes = base64.b64decode(msg.data)
            frame = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().warn(f'Drone {drone_id}: failed to decode camera frame: {e}')
            return

        if frame is None:
            return

        height, width = frame.shape[:2]
        results = self.model(frame, verbose=False)

        detections = []
        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)]
                conf = float(box.conf)
                if conf > CONFIDENCE_THRESHOLD:
                    x, y, w, h = box.xywh[0].tolist()
                    detections.append({
                        'label': label,
                        'confidence': round(conf, 2),
                        'center': (int(x), int(y)),
                        'frame_width': width,
                        'frame_height': height,
                    })

        if detections:
            out = String()
            out.data = json.dumps(detections)
            self.detection_publishers[drone_id].publish(out)
            self.get_logger().info(
                f'Drone {drone_id} detected: '
                f'{[(d["label"], d["confidence"]) for d in detections]}'
            )


def main():
    rclpy.init()
    vision = RealVisionNode()
    try:
        rclpy.spin(vision)
    except KeyboardInterrupt:
        pass
    vision.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
