import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from grid import create_grid
from astar import astar
from targets import place_targets, prioritize_targets

grid = create_grid()
targets = place_targets(grid)
ordered = prioritize_targets((0,0), targets)

fig, ax = plt.subplots(figsize=(8,8))
drone_pos = (0, 0)

for target in ordered:
    path = astar(grid, drone_pos, target)
    for pos in path:
        ax.clear()
        display = [row[:] for row in grid.tolist()]
        ax.imshow(grid, cmap='Greys', vmin=0, vmax=2)
        ax.plot(pos[1], pos[0], 'bs', markersize=12, label='Drone')
        for t in targets:
            ax.plot(t[1], t[0], 'r*', markersize=14)
        ax.set_title(f'Drone navigating to target {target}')
        ax.legend()
        plt.pause(0.08)
        drone_pos = pos

print('Mission complete.')
plt.show()