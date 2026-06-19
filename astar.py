import heapq

def heuristic(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def astar(grid, start, goal):
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]

        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nbr = (current[0]+dx, current[1]+dy)
            if 0<=nbr[0]<len(grid) and 0<=nbr[1]<len(grid[0]):
                if grid[nbr[0]][nbr[1]] == 1:
                    continue
                g = g_score[current] + 1
                if g < g_score.get(nbr, float('inf')):
                    came_from[nbr] = current
                    g_score[nbr] = g
                    f = g + heuristic(nbr, goal)
                    heapq.heappush(open_set, (f, nbr))
    return []
