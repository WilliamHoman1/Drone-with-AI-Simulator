import numpy as np

GRID_SIZE = 20
OBSTACLE_DENSITY = 0.2

def create_grid():
    grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
    obstacles = np.random.rand(GRID_SIZE, GRID_SIZE) < OBSTACLE_DENSITY
    grid[obstacles] = 1
    grid[0][0] = 0
    grid[19][19] = 0
    return grid
