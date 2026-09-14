"""Unit tests for the swarm's task allocation.

These cover the behaviour that is genuinely hard to verify by watching the
simulation run: preemption, deduplication, cooldowns and timeouts all depend on
timing and on state you can't see from outside.

Time is injected rather than read from the clock, so nothing here sleeps.
"""
import pytest

from task_allocation import Alert, Assign, Resolve, TaskAllocator

# Three drones spread along x, all at y=0, so distances are easy to reason about.
HOMES = {1: (0.0, 0.0), 2: (50.0, 0.0), 3: (100.0, 0.0)}


def contact(label='car', tier='medium', x=0.0, y=0.0, conf=0.9):
    return {'label': label, 'tier': tier, 'confidence': conf, 'world': [x, y]}


def alloc(**kw):
    return TaskAllocator(HOMES, **kw)


def only(decisions, kind):
    return [d for d in decisions if isinstance(d, kind)]


# --------------------------------------------------------------- assignment

def test_assigns_the_nearest_free_drone():
    a = alloc()
    decisions = a.observe(1, [contact(x=48.0)], now=0.0)

    assigns = only(decisions, Assign)
    assert len(assigns) == 1
    assert assigns[0].drone_id == 2  # drone 2 sits at x=50, closest to x=48
    assert a.drones[2].status == 'investigating'


def test_reporting_drone_is_not_automatically_the_assigned_drone():
    """Drone 1 sees something on the far side of the map; drone 3 should go."""
    a = alloc()
    decisions = a.observe(1, [contact(x=99.0)], now=0.0)
    assert only(decisions, Assign)[0].drone_id == 3


def test_queues_when_every_drone_is_busy():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', x=x)], now=0.0)
    assert all(d.status == 'investigating' for d in a.drones.values())

    decisions = a.observe(1, [contact(label='truck', x=25.0)], now=0.0)
    assert only(decisions, Assign) == []
    target = next(t for t in a.targets.values() if t.label == 'truck')
    assert target.assigned_drone is None


def test_tick_assigns_a_queued_target_once_a_drone_frees_up():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', x=x)], now=0.0)
    a.observe(1, [contact(label='truck', x=25.0)], now=0.0)

    a.scan_complete('car1', 50.0, 0.0, 'VEHICLE', now=1.0)
    assigns = only(a.tick(now=2.0), Assign)

    assert len(assigns) == 1
    assert assigns[0].target.label == 'truck'


def test_tick_prefers_the_most_urgent_queued_target():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', tier='high', x=x)], now=0.0)
    a.observe(1, [contact(label='bag', tier='low', x=24.0)], now=0.0)
    a.observe(1, [contact(label='person', tier='high', x=26.0)], now=0.0)

    a.scan_complete('car1', 50.0, 0.0, 'VEHICLE', now=1.0)
    assigns = only(a.tick(now=2.0), Assign)

    assert assigns[0].target.label == 'person'


# --------------------------------------------------------------- preemption

def test_high_priority_preempts_a_lower_priority_investigation():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', tier='medium', x=x)], now=0.0)

    decisions = a.observe(1, [contact(label='person', tier='high', x=49.0)], now=1.0)
    assigns = only(decisions, Assign)

    assert len(assigns) == 1
    assert assigns[0].drone_id == 2
    assert assigns[0].preempted is not None


def test_preempted_target_is_requeued_not_dropped():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', tier='medium', x=x)], now=0.0)
    decisions = a.observe(1, [contact(label='person', tier='high', x=49.0)], now=1.0)

    preempted_id = only(decisions, Assign)[0].preempted
    assert preempted_id in a.targets                       # still tracked
    assert a.targets[preempted_id].assigned_drone is None   # back in the pool


def test_high_priority_does_not_preempt_another_high_priority():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'p{i}', tier='high', x=x)], now=0.0)

    decisions = a.observe(1, [contact(label='person', tier='high', x=49.0)], now=1.0)
    assert only(decisions, Assign) == []


def test_equal_tier_does_not_preempt():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', tier='medium', x=x)], now=0.0)

    decisions = a.observe(1, [contact(label='truck', tier='medium', x=49.0)], now=1.0)
    assert only(decisions, Assign) == []


def test_low_priority_never_preempts():
    a = alloc()
    for i, x in enumerate([0.0, 50.0, 100.0]):
        a.observe(1, [contact(label=f'car{i}', tier='medium', x=x)], now=0.0)

    decisions = a.observe(1, [contact(label='bag', tier='low', x=49.0)], now=1.0)
    assert only(decisions, Assign) == []


# -------------------------------------------------------------- deduplication

def test_same_contact_seen_repeatedly_creates_one_target():
    a = alloc(dedupe_radius=5.0)
    a.observe(1, [contact(label='person', x=10.0)], now=0.0)
    for t in range(1, 10):
        a.observe(1, [contact(label='person', x=10.2)], now=float(t))
    assert a.active_target_count == 1


def test_repeat_sighting_does_not_re_alert():
    a = alloc()
    first = a.observe(1, [contact(label='person', tier='high', x=10.0)], now=0.0)
    second = a.observe(1, [contact(label='person', tier='high', x=10.5)], now=1.0)

    assert len(only(first, Alert)) == 1
    assert only(second, Alert) == []


def test_same_label_outside_dedupe_radius_is_a_separate_target():
    a = alloc(dedupe_radius=5.0)
    a.observe(1, [contact(label='person', x=10.0)], now=0.0)
    a.observe(1, [contact(label='person', x=20.0)], now=1.0)
    assert a.active_target_count == 2


def test_different_label_at_the_same_place_is_a_separate_target():
    a = alloc()
    a.observe(1, [contact(label='person', x=10.0)], now=0.0)
    a.observe(1, [contact(label='car', x=10.0)], now=1.0)
    assert a.active_target_count == 2


def test_two_drones_reporting_the_same_object_do_not_double_task():
    a = alloc(dedupe_radius=5.0)
    a.observe(1, [contact(label='person', x=48.0)], now=0.0)
    decisions = a.observe(2, [contact(label='person', x=48.4)], now=0.1)

    assert a.active_target_count == 1
    assert only(decisions, Assign) == []


# ------------------------------------------------------------------ alerting

@pytest.mark.parametrize('tier,expected', [('high', 1), ('medium', 0), ('low', 0)])
def test_only_high_priority_contacts_raise_an_alert(tier, expected):
    a = alloc()
    decisions = a.observe(1, [contact(label='thing', tier=tier, x=5.0)], now=0.0)
    assert len(only(decisions, Alert)) == expected


# ------------------------------------------------------------ scan / resolve

def test_scan_result_resolves_the_target_and_frees_the_drone():
    a = alloc()
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    assert a.drones[2].status == 'investigating'

    decisions = a.scan_complete('car', 48.0, 0.0, 'VEHICLE — TRANSPORT', now=5.0)

    assert len(only(decisions, Resolve)) == 1
    assert a.active_target_count == 0
    assert a.drones[2].status == 'patrolling'
    assert a.drones[2].current_target is None


def test_scan_result_matching_nothing_is_ignored():
    a = alloc()
    assert a.scan_complete('ghost', 5.0, 5.0, 'NOTHING', now=1.0) == []


def test_scan_result_matches_within_the_match_radius_only():
    a = alloc(scan_match_radius=10.0)
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)

    assert a.scan_complete('car', 70.0, 0.0, 'VEHICLE', now=1.0) == []   # too far
    assert a.scan_complete('car', 52.0, 0.0, 'VEHICLE', now=2.0) != []   # in range


# ------------------------------------------------------------------ cooldown

def test_cleared_contact_is_not_immediately_re_detected():
    a = alloc(resolved_cooldown=45.0)
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    a.scan_complete('car', 48.0, 0.0, 'VEHICLE', now=5.0)

    a.observe(1, [contact(label='car', x=48.0)], now=6.0)
    assert a.active_target_count == 0


def test_cooldown_expires_and_the_contact_can_be_re_detected():
    a = alloc(resolved_cooldown=45.0)
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    a.scan_complete('car', 48.0, 0.0, 'VEHICLE', now=5.0)

    a.tick(now=100.0)  # prunes the expired cooldown entry
    a.observe(1, [contact(label='car', x=48.0)], now=101.0)
    assert a.active_target_count == 1


def test_cooldown_expiry_does_not_depend_on_a_tick():
    """The age check has to live in the cooldown test itself.

    Without this, the suite passes even if the cooldown never expires, because
    tick() prunes stale entries on a separate code path — the expiry test above
    would be exercising the prune rather than the thing it names.
    """
    a = alloc(resolved_cooldown=45.0)
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    a.scan_complete('car', 48.0, 0.0, 'VEHICLE', now=5.0)

    a.observe(1, [contact(label='car', x=48.0)], now=101.0)  # no tick in between
    assert a.active_target_count == 1


def test_cooldown_is_scoped_to_the_cleared_location():
    a = alloc(resolved_cooldown=45.0, dedupe_radius=5.0)
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    a.scan_complete('car', 48.0, 0.0, 'VEHICLE', now=5.0)

    # A different car well away from the cleared one is still a live contact.
    a.observe(1, [contact(label='car', x=20.0)], now=6.0)
    assert a.active_target_count == 1


# ------------------------------------------------------------------- timeout

def test_stalled_investigation_times_out_and_frees_the_drone():
    a = alloc(investigation_timeout=45.0)
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)

    assert only(a.tick(now=10.0), Resolve) == []       # still within budget
    decisions = a.tick(now=100.0)                       # well past it

    assert len(only(decisions, Resolve)) == 1
    assert a.drones[2].status == 'patrolling'


# ------------------------------------------------------------------ location

def test_world_coordinates_are_used_when_the_sensor_supplies_them():
    a = alloc()
    a.observe(1, [contact(label='car', x=42.0, y=7.0)], now=0.0)
    target = next(iter(a.targets.values()))
    assert (target.x, target.y) == (42.0, 7.0)


def test_falls_back_to_an_offset_estimate_without_world_coordinates():
    a = alloc()
    a.update_position(1, 10.0, 20.0)
    a.observe(1, [{'label': 'car', 'tier': 'medium', 'center': [64, 128]}], now=0.0)

    target = next(iter(a.targets.values()))
    assert target.x == pytest.approx(11.0)   # 10 + 64/64
    assert target.y == pytest.approx(22.0)   # 20 + 128/64


# --------------------------------------------------------------------- misc

def test_reset_clears_all_mission_state():
    a = alloc()
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    a.scan_complete('car', 48.0, 0.0, 'VEHICLE', now=1.0)
    a.observe(1, [contact(label='person', tier='high', x=5.0)], now=2.0)

    a.reset()

    assert a.active_target_count == 0
    assert a.resolved == []
    assert all(d.status == 'patrolling' for d in a.drones.values())
    assert all(d.current_target is None for d in a.drones.values())


def test_detections_from_an_unknown_drone_are_ignored():
    a = alloc()
    assert a.observe(99, [contact()], now=0.0) == []
    assert a.active_target_count == 0


def test_status_snapshot_reports_drone_state_and_target_count():
    a = alloc()
    a.observe(1, [contact(label='car', x=48.0)], now=0.0)
    snap = a.status_snapshot()

    assert snap['active_targets'] == 1
    assert snap['drones'][2]['status'] == 'investigating'
    assert set(snap['drones']) == {1, 2, 3}
