"""Task allocation for the drone swarm — pure Python, no ROS.

This is the interesting part of the system: given contacts reported by several
drones, decide who goes where, and let an urgent contact interrupt a drone that
is already busy with a less urgent one.

It is deliberately separate from ``swarm_coordinator.py`` (the ROS adapter) so
it can be unit tested without a ROS graph, Unity, or a wall clock — every method
takes ``now`` explicitly, which makes the cooldown and timeout behaviour
deterministic under test.

The allocator never publishes anything. It returns *decisions*; the adapter is
responsible for turning those into ROS messages.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
import math

# Ordering matters: a contact only preempts one that is strictly less urgent.
TIER_RANK = {'low': 0, 'medium': 1, 'high': 2}


@dataclass
class Target:
    id: int
    x: float
    y: float
    label: str
    tier: str
    detected_by: int
    confidence: float = 0.0
    assigned_drone: Optional[int] = None
    created_at: float = 0.0
    assigned_at: Optional[float] = None

    @property
    def rank(self) -> int:
        return TIER_RANK.get(self.tier, 0)


@dataclass
class DroneState:
    x: float = 0.0
    y: float = 0.0
    status: str = 'patrolling'
    current_target: Optional[int] = None


# ----------------------------------------------------------------- decisions

@dataclass
class Alert:
    """A high-priority contact worth escalating to the operator."""
    target: Target


@dataclass
class Assign:
    """Send ``drone_id`` to investigate ``target``."""
    drone_id: int
    target: Target
    preempted: Optional[int] = None


@dataclass
class Resolve:
    """``target`` is closed out; whichever drone held it is free."""
    target: Target
    reason: str


Decision = object  # Alert | Assign | Resolve


class TaskAllocator:
    def __init__(
        self,
        drone_home: Dict[int, Sequence[float]],
        *,
        dedupe_radius: float = 5.0,
        resolved_cooldown: float = 45.0,
        investigation_timeout: float = 45.0,
        scan_match_radius: float = 10.0,
    ):
        self.drones: Dict[int, DroneState] = {
            i: DroneState(x=float(p[0]), y=float(p[1])) for i, p in drone_home.items()
        }
        self.targets: Dict[int, Target] = {}
        self.resolved: List[dict] = []
        self.counter = 0

        self.dedupe_radius = dedupe_radius
        self.resolved_cooldown = resolved_cooldown
        self.investigation_timeout = investigation_timeout
        self.scan_match_radius = scan_match_radius

    # ------------------------------------------------------------- ingestion

    def update_position(self, drone_id: int, x: float, y: float) -> None:
        drone = self.drones.get(drone_id)
        if drone is not None:
            drone.x, drone.y = float(x), float(y)

    def observe(self, drone_id: int, detections: Sequence[dict], now: float) -> List[Decision]:
        """Take one drone's sensor report and decide what to do about it."""
        decisions: List[Decision] = []
        if drone_id not in self.drones:
            return decisions

        for det in detections:
            x, y = self._locate(drone_id, det)
            label = det.get('label', 'unknown')

            # A sensor re-reports the same object every scan. Refresh the
            # existing target rather than piling up duplicates and re-alerting.
            existing = self._active_near(label, x, y)
            if existing is not None:
                existing.created_at = now
                continue

            if self._in_cooldown(label, x, y, now):
                continue

            self.counter += 1
            target = Target(
                id=self.counter, x=x, y=y, label=label,
                tier=det.get('tier', 'low'),
                confidence=float(det.get('confidence', 0.0)),
                detected_by=drone_id, created_at=now,
            )
            self.targets[target.id] = target

            if target.tier == 'high':
                decisions.append(Alert(target))

            assignment = self._assign(target, now)
            if assignment is not None:
                decisions.append(assignment)

        return decisions

    def scan_complete(self, label: str, x: float, y: float, result: str,
                      now: float) -> List[Decision]:
        """A drone finished classifying a contact — close the target out.

        This, not proximity, is what completes an investigation: the drone
        stands off while scanning and never gets close enough for a distance
        check to fire.
        """
        match = next(
            (t for t in self.targets.values()
             if t.label == label
             and math.hypot(t.x - x, t.y - y) < self.scan_match_radius),
            None,
        )
        if match is None:
            return []
        return self._resolve(match.id, f'classified as {result}', now)

    def tick(self, now: float) -> List[Decision]:
        """Periodic housekeeping: time out stalled work, retry the queue."""
        decisions: List[Decision] = []

        # Safety net. If a scan result never arrives (Unity closed, the scan
        # component missing) don't strand the drone in 'investigating' forever.
        for drone_id, drone in list(self.drones.items()):
            if drone.status != 'investigating' or drone.current_target is None:
                continue
            target = self.targets.get(drone.current_target)
            if target is None:
                drone.status = 'patrolling'
                drone.current_target = None
            elif now - (target.assigned_at or target.created_at) > self.investigation_timeout:
                decisions += self._resolve(target.id, 'investigation timed out', now)

        self.resolved = [r for r in self.resolved
                         if now - r['time'] < self.resolved_cooldown]

        # Anything queued or preempted gets another look now that a drone may
        # have come free. Sort so the most urgent goes first.
        pending = sorted(
            (t for t in self.targets.values() if t.assigned_drone is None),
            key=lambda t: -t.rank,
        )
        for target in pending:
            assignment = self._assign(target, now)
            if assignment is not None:
                decisions.append(assignment)

        return decisions

    # --------------------------------------------------------------- internals

    def _locate(self, drone_id: int, det: dict):
        """Exact ground coordinates when the sensor supplies them, else a rough
        estimate offset from the reporting drone."""
        world = det.get('world')
        if world:
            return float(world[0]), float(world[1])

        drone = self.drones[drone_id]
        center = det.get('center') or (0, 0)
        return drone.x + center[0] / 64.0, drone.y + center[1] / 64.0

    def _active_near(self, label: str, x: float, y: float) -> Optional[Target]:
        return next(
            (t for t in self.targets.values()
             if t.label == label
             and math.hypot(t.x - x, t.y - y) < self.dedupe_radius),
            None,
        )

    def _in_cooldown(self, label: str, x: float, y: float, now: float) -> bool:
        return any(
            r['label'] == label
            and math.hypot(r['x'] - x, r['y'] - y) < self.dedupe_radius
            and now - r['time'] < self.resolved_cooldown
            for r in self.resolved
        )

    def _distance(self, drone_id: int, target: Target) -> float:
        drone = self.drones[drone_id]
        return math.hypot(drone.x - target.x, drone.y - target.y)

    def _assign(self, target: Target, now: float) -> Optional[Assign]:
        best, best_dist = None, float('inf')

        # Prefer a drone that isn't doing anything — no work is lost.
        for drone_id, drone in self.drones.items():
            if drone.status != 'patrolling':
                continue
            d = self._distance(drone_id, target)
            if d < best_dist:
                best, best_dist = drone_id, d

        preempted = None
        if best is None:
            # Nobody free. An urgent contact may pull a drone off strictly less
            # urgent work rather than queueing behind it.
            for drone_id, drone in self.drones.items():
                if drone.status != 'investigating':
                    continue
                current = self.targets.get(drone.current_target)
                if current is None or current.rank >= target.rank:
                    continue
                d = self._distance(drone_id, target)
                if d < best_dist:
                    best, best_dist, preempted = drone_id, d, current.id

        if best is None:
            return None

        if preempted is not None:
            # Back into the pool unassigned, so it gets picked up again rather
            # than being silently dropped.
            self.targets[preempted].assigned_drone = None
            self.targets[preempted].assigned_at = None

        target.assigned_drone = best
        target.assigned_at = now
        self.drones[best].status = 'investigating'
        self.drones[best].current_target = target.id
        return Assign(drone_id=best, target=target, preempted=preempted)

    def _resolve(self, target_id: int, reason: str, now: float) -> List[Decision]:
        target = self.targets.pop(target_id, None)
        if target is None:
            return []

        for drone in self.drones.values():
            if drone.current_target == target_id:
                drone.status = 'patrolling'
                drone.current_target = None

        self.resolved.append(
            {'label': target.label, 'x': target.x, 'y': target.y, 'time': now})
        return [Resolve(target=target, reason=reason)]

    def reset(self) -> None:
        """Drop all mission state — used when the operator restarts the run."""
        self.targets.clear()
        self.resolved.clear()
        self.counter = 0
        for drone in self.drones.values():
            drone.status = 'patrolling'
            drone.current_target = None

    # ------------------------------------------------------------- reporting

    @property
    def active_target_count(self) -> int:
        return len(self.targets)

    def status_snapshot(self) -> dict:
        return {
            'drones': {
                i: {'x': d.x, 'y': d.y, 'status': d.status,
                    'current_target': d.current_target}
                for i, d in self.drones.items()
            },
            'active_targets': len(self.targets),
        }
