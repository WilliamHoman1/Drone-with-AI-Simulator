"""ROS adapter around TaskAllocator.

All the decision-making lives in task_allocation.py, which has no ROS
dependencies and is unit tested. This module's only jobs are to feed sensor
reports and positions in, and to turn the decisions that come back into
messages on the right topics.
"""
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped

from ros_utils import safe_json
from task_allocation import Alert, Assign, Resolve, TaskAllocator

# Sector centres of the 60 x 30 search area (see SearchPattern.cs). Overwritten
# by Unity's real positions as soon as they arrive.
DRONE_HOME = {1: (10.0, 15.0), 2: (30.0, 15.0), 3: (50.0, 15.0)}


class SwarmCoordinator(Node):
    def __init__(self):
        super().__init__('swarm_coordinator')

        self.allocator = TaskAllocator(DRONE_HOME)

        for drone_id in DRONE_HOME:
            self.create_subscription(
                String, f'/drone_{drone_id}/detections',
                lambda msg, i=drone_id: self.detection_cb(msg, i), 10)
            self.create_subscription(
                PoseStamped, f'/drone_{drone_id}/position',
                lambda msg, i=drone_id: self.position_cb(msg, i), 10)

        self.mission_publishers = {
            i: self.create_publisher(String, f'/drone_{i}/mission', 10)
            for i in DRONE_HOME
        }
        self.status_publisher = self.create_publisher(String, '/swarm/status', 10)
        self.alert_publisher = self.create_publisher(String, '/swarm/alerts', 10)

        # Unity's TargetScan reports here once a drone has orbited a contact and
        # classified it.
        self.create_subscription(
            String, '/swarm/scan_result', self.scan_result_cb, 10)
        # Unity publishes here when the operator restarts the mission.
        self.create_subscription(String, '/swarm/reset', self.reset_cb, 10)

        self.timer = self.create_timer(2.0, self.coordinate)
        self.get_logger().info('Swarm coordinator online')

    # ------------------------------------------------------------- callbacks

    def position_cb(self, msg, drone_id):
        self.allocator.update_position(
            drone_id, msg.pose.position.x, msg.pose.position.z)

    def detection_cb(self, msg, drone_id):
        detections = safe_json(self, msg, 'detection')
        if detections is None:
            return
        self.apply(self.allocator.observe(drone_id, detections, time.time()))

    def scan_result_cb(self, msg):
        scan = safe_json(self, msg, 'scan result')
        if scan is None:
            return
        decisions = self.allocator.scan_complete(
            scan['label'], float(scan['x']), float(scan['z']),
            scan.get('result', 'classified'), time.time())
        if not decisions:
            self.get_logger().warn(
                f"Scan result for {scan['label']} at "
                f"({scan['x']}, {scan['z']}) matched no active target")
        self.apply(decisions)

    def reset_cb(self, msg):
        self.allocator.reset()
        self.get_logger().info('Mission reset — cleared all targets and assignments')

    def coordinate(self):
        self.apply(self.allocator.tick(time.time()))

        status = String()
        status.data = json.dumps(self.allocator.status_snapshot(), default=str)
        self.status_publisher.publish(status)

    # ---------------------------------------------------------- decision sink

    def apply(self, decisions):
        for d in decisions:
            if isinstance(d, Alert):
                self.publish_alert(d.target)
            elif isinstance(d, Assign):
                self.publish_mission(d)
            elif isinstance(d, Resolve):
                self.get_logger().info(
                    f'Target #{d.target.id} ({d.target.label}) resolved — {d.reason}')

    def publish_alert(self, target):
        msg = String()
        msg.data = json.dumps({
            'target_id': target.id,
            'label': target.label,
            'confidence': target.confidence,
            'detected_by': target.detected_by,
            'x': round(target.x, 1),
            'y': round(target.y, 1),
            'time': time.strftime('%H:%M:%S'),
        })
        self.alert_publisher.publish(msg)
        self.get_logger().info(
            f'ALERT: high-priority target #{target.id} ({target.label})')

    def publish_mission(self, assign):
        target = assign.target
        msg = String()
        msg.data = json.dumps([[round(target.x, 1), round(target.y, 1)]])
        self.mission_publishers[assign.drone_id].publish(msg)

        if assign.preempted is not None:
            self.get_logger().info(
                f'Drone {assign.drone_id} pulled off target #{assign.preempted} '
                f'to respond to higher-priority target #{target.id}')
        self.get_logger().info(
            f'Drone {assign.drone_id} assigned to investigate {target.label} '
            f'[{target.tier}] at ({target.x:.1f}, {target.y:.1f})')


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
