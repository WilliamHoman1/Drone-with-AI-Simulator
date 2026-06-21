import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import requests
import random
import time

fig = plt.figure(figsize=(14, 8))
fig.patch.set_facecolor('#0a0a0f')

# 3D simulation on left
ax3d = fig.add_subplot(121, projection='3d')
ax3d.set_facecolor('#0a0a0f')

# Detection log on right
ax_log = fig.add_subplot(122)
ax_log.set_facecolor('#0a0a0f')
ax_log.axis('off')

# Drone state
drones = {
    1: {'pos': np.array([0.0, 0.0, 10.0]), 'target': np.array([10.0, 5.0, 10.0]), 'color': '#4a9eff', 'trail': []},
    2: {'pos': np.array([20.0, 0.0, 10.0]), 'target': np.array([25.0, 10.0, 10.0]), 'color': '#4aff9e', 'trail': []},
    3: {'pos': np.array([10.0, 20.0, 10.0]), 'target': np.array([15.0, 25.0, 10.0]), 'color': '#b44aff', 'trail': []}
}

# Patrol waypoints per drone
waypoints = {
    1: [[0,0,10],[10,0,10],[10,10,10],[0,10,10]],
    2: [[20,0,10],[30,0,10],[30,10,10],[20,10,10]],
    3: [[10,20,10],[20,20,10],[20,30,10],[10,30,10]]
}
wp_idx = {1: 0, 2: 0, 3: 0}

detections = []
detection_markers = []

def get_swarm_data():
    try:
        r = requests.get('http://localhost:8000/state', timeout=1)
        return r.json()
    except:
        return None

def update(frame):
    ax3d.cla()
    ax3d.set_facecolor('#0a0a0f')

    # Draw ground grid
    xx, yy = np.meshgrid(range(0, 40, 5), range(0, 40, 5))
    ax3d.plot_surface(xx, yy, np.zeros_like(xx),
                      alpha=0.1, color='#1a3a5c')

    # Draw patrol zones
    zone_corners = [
        [(0,0),(10,0),(10,10),(0,10),(0,0)],
        [(20,0),(30,0),(30,10),(20,10),(20,0)],
        [(10,20),(20,20),(20,30),(10,30),(10,20)]
    ]
    zone_colors = ['#4a9eff', '#4aff9e', '#b44aff']
    for corners, color in zip(zone_corners, zone_colors):
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        ax3d.plot(xs, ys, [0]*len(xs), color=color, alpha=0.3, linewidth=1)

    # Try to get real data from swarm API
    swarm_data = get_swarm_data()

    for drone_id, drone in drones.items():
        # Update target from API or use patrol waypoints
        if swarm_data and str(drone_id) in str(swarm_data.get('drones', {})):
            try:
                api_drone = swarm_data['drones'][str(drone_id)]
                drone['target'] = np.array([
                    float(api_drone['x']),
                    float(api_drone['y']),
                    10.0
                ])
            except:
                pass
        else:
            # Patrol waypoints
            wp = waypoints[drone_id][wp_idx[drone_id]]
            drone['target'] = np.array(wp, dtype=float)
            dist = np.linalg.norm(drone['pos'] - drone['target'])
            if dist < 1.0:
                wp_idx[drone_id] = (wp_idx[drone_id] + 1) % len(waypoints[drone_id])

        # Move drone toward target
        direction = drone['target'] - drone['pos']
        dist = np.linalg.norm(direction)
        if dist > 0.5:
            drone['pos'] += direction / dist * 0.4

        # Add to trail
        drone['trail'].append(drone['pos'].copy())
        if len(drone['trail']) > 30:
            drone['trail'].pop(0)

        # Draw trail
        if len(drone['trail']) > 1:
            trail = np.array(drone['trail'])
            ax3d.plot(trail[:,0], trail[:,1], trail[:,2],
                     color=drone['color'], alpha=0.3, linewidth=1)

        # Draw drone body
        ax3d.scatter(*drone['pos'], color=drone['color'],
                    s=150, zorder=5, marker='D')

        # Draw rotor arms
        for dx, dy in [(0.8,0),(-0.8,0),(0,0.8),(0,-0.8)]:
            ax3d.plot([drone['pos'][0], drone['pos'][0]+dx],
                     [drone['pos'][1], drone['pos'][1]+dy],
                     [drone['pos'][2], drone['pos'][2]],
                     color=drone['color'], linewidth=2, alpha=0.8)

        # Label
        ax3d.text(drone['pos'][0], drone['pos'][1], drone['pos'][2]+1.5,
                 f'D{drone_id}', color=drone['color'],
                 fontsize=9, fontweight='bold')

        # Altitude line
        ax3d.plot([drone['pos'][0], drone['pos'][0]],
                 [drone['pos'][1], drone['pos'][1]],
                 [0, drone['pos'][2]],
                 color=drone['color'], alpha=0.2, linewidth=1, linestyle='--')

        # Random detection
        if random.random() < 0.03:
            det = {
                'pos': drone['pos'].copy(),
                'drone': drone_id,
                'label': random.choice(['vehicle', 'person', 'truck']),
                'conf': round(random.uniform(0.75, 0.98), 2),
                'time': time.strftime('%H:%M:%S'),
                'color': drone['color']
            }
            detections.insert(0, det)
            if len(detections) > 10:
                detections.pop()

    # Draw detection markers
    for det in detections:
        ax3d.scatter(det['pos'][0], det['pos'][1], 0,
                    color='red', s=80, marker='x', zorder=4)
        ax3d.plot([det['pos'][0], det['pos'][0]],
                 [det['pos'][1], det['pos'][1]],
                 [0, det['pos'][2]],
                 color='red', alpha=0.2, linewidth=1, linestyle=':')

    # Style 3D plot
    ax3d.set_xlim([-5, 40])
    ax3d.set_ylim([-5, 40])
    ax3d.set_zlim([0, 20])
    ax3d.set_xlabel('X', color='white', fontsize=8)
    ax3d.set_ylabel('Y', color='white', fontsize=8)
    ax3d.set_zlabel('Alt', color='white', fontsize=8)
    ax3d.tick_params(colors='#444')
    ax3d.set_title('UAV Swarm — Live 3D View', color='white',
                  fontsize=12, fontweight='bold', pad=10)
    ax3d.xaxis.pane.fill = False
    ax3d.yaxis.pane.fill = False
    ax3d.zaxis.pane.fill = False
    ax3d.xaxis.pane.set_edgecolor('#1a2a3a')
    ax3d.yaxis.pane.set_edgecolor('#1a2a3a')
    ax3d.zaxis.pane.set_edgecolor('#1a2a3a')
    ax3d.view_init(elev=30, azim=frame*0.5)  # slowly rotate

    # Detection log panel
    ax_log.cla()
    ax_log.set_facecolor('#0a0a0f')
    ax_log.axis('off')
    ax_log.set_title('Detection Log', color='white',
                    fontsize=12, fontweight='bold')

    y_pos = 0.95
    for det in detections[:8]:
        ax_log.text(0.05, y_pos,
                   f"[{det['time']}] Drone {det['drone']}",
                   color=det['color'], fontsize=9,
                   transform=ax_log.transAxes)
        ax_log.text(0.05, y_pos - 0.04,
                   f"  {det['label'].upper()} — conf: {det['conf']}",
                   color='white', fontsize=10, fontweight='bold',
                   transform=ax_log.transAxes)
        y_pos -= 0.11

    if not detections:
        ax_log.text(0.05, 0.5, 'Scanning...',
                   color='#444', fontsize=12,
                   transform=ax_log.transAxes)

    # Status bar
    fig.text(0.5, 0.02,
            f'DRONES ACTIVE: 3/3   |   DETECTIONS: {len(detections)}   |   STATUS: OPERATIONAL',
            color='#4a9eff', fontsize=9, ha='center',
            fontfamily='monospace')

ani = animation.FuncAnimation(fig, update, frames=720,
                               interval=100, blit=False)

plt.tight_layout()
plt.show()