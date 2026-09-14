"""Small helpers shared by the ROS nodes in this package."""
import json


def safe_json(node, msg, what):
    """Parse a ROS String payload, logging and skipping malformed messages.

    An exception raised inside a ROS callback propagates out of the executor and
    takes the whole node down. One malformed frame from Unity would otherwise
    silently stop all tasking, or kill the dashboard bridge, for the rest of the
    run — with nothing in the logs tying the dead node to the bad message.
    """
    try:
        return json.loads(msg.data)
    except (json.JSONDecodeError, TypeError) as e:
        node.get_logger().warn(f'Bad {what} payload ({e}): {msg.data[:120]!r}')
        return None
