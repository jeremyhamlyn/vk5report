"""Maidenhead grid locator to lat/lon converter."""

def grid_to_latlon(grid):
    """Convert a Maidenhead grid square (4 or 6 char) to (lat, lon) centre point.
    Returns (None, None) for invalid input."""
    if not grid or len(grid) < 4:
        return None, None
    grid = grid.upper().strip()
    try:
        lon = (ord(grid[0]) - ord('A')) * 20 - 180
        lat = (ord(grid[1]) - ord('A')) * 10 - 90
        lon += int(grid[2]) * 2
        lat += int(grid[3]) * 1
        if len(grid) >= 6:
            lon += (ord(grid[4]) - ord('A')) * (2 / 24)
            lat += (ord(grid[5]) - ord('A')) * (1 / 24)
            lon += 1 / 24        # centre of subsquare
            lat += 0.5 / 24
        else:
            lon += 1.0           # centre of 2° field
            lat += 0.5
        return round(lat, 5), round(lon, 5)
    except Exception:
        return None, None


def is_valid_grid(grid):
    if not grid or len(grid) < 4:
        return False
    g = grid.upper()
    if not (g[0].isalpha() and g[1].isalpha() and g[2].isdigit() and g[3].isdigit()):
        return False
    return True
