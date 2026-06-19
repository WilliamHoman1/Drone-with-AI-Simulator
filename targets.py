import random

def place_targets(grid, n=4):
    targets = []
    while len(targets) < n:
        r, c = random.randint(0, 19), random.randint(0, 19)
        if grid[r][c] == 0 and (r, c) != (0, 0):
            grid[r][c] = 2
            targets.append((r, c))
    return targets


def prioritize_targets(start, targets):
    remaining = targets.copy()
    ordered = []
    current = start
    while remaining:
        nearest = min(remaining, key=lambda t: abs(t[0] - current[0]) + abs(t[1] - current[1]))
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest
    return ordered
