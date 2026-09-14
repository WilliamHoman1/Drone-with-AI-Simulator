"""Put swarm/ on the path so task_allocation imports the same way the ROS node does."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'swarm'))
