from pathlib import Path
import os
import polars as pl
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx
from shapely.geometry import LineString
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm


"""
Begin of parsing and database storing
"""


data_dir = Path(os.getcwd() + "/data")
log_df = pl.DataFrame(
    {
        "Time":[],
        "Satellite Count":[],
        "Latitude":[],
        "Longitude":[],
        "Speed Over Ground (knots)":[],
        "Elevation (m)":[],
    },
    {
        "Time":str,
        "Satellite Count":int,
        "Latitude":float,
        "Longitude":float,
        "Speed Over Ground (knots)":float,
        "Elevation (m)":float,
    }
)
tmp_df = pl.DataFrame(
    {
        "Time":[],
        "Temperature (C)":[],
    },
    {
        "Time":str,
        "Temperature (C)":float
    }
)

log_files = [f for f in data_dir.iterdir() if f.is_file() and "GPSLOG" in f.name]
log_files.sort()
tmp_files = [f for f in data_dir.iterdir() if f.is_file() and "TMPLOG" in f.name]
tmp_files.sort()


def log_parse(log, file):
    data = log.split("$")
    while data[0].startswith("GPGGA") == False:
        data.pop(0)
    for i in range(0, len(data), 2):
        data[i] = data[i].split(",")
        if data[i][0] == "GPGGA":
            try: 
                time = str(int(float(data[i][1])))
                time = time[0] + time[1] + ":" + time[2] + time[3] + ":" + time[4] + time[5]
            except ValueError:
                time = "Error"
            try:
                satellite = int(data[i][7])
            except ValueError:
                satellite = -1
            try:
                deg = float(data[i][2][:2])
                minutes = float(data[i][2][2:]) / 60
                lat = deg + minutes
                if data[i][3] == "S":
                    lat *= -1
            except ValueError:
                lat = "ERROR"
            try:
                deg = float(data[i][4][:3])
                minutes = float(data[i][4][3:]) / 60
                long = deg + minutes
                if data[i][5] == "W":
                    long *= -1
            except ValueError:
                long = 'ERROR'
            try:
                speed = float(data[i+1][7])
            except ValueError:
                speed = -1.0
            try:
                elevation = float(data[i][9])
            except ValueError:
                elevation = -1.0
            if lat != "ERROR" and long != "ERROR":
                d = pl.DataFrame(
                    {
                        "Time":[time], 
                        "Satellite Count":[satellite], 
                        "Latitude":[lat],
                        "Longitude":[long],
                        "Speed Over Ground (knots)":[speed],
                        'Elevation (m)':[elevation]})
                log_df.extend(d)

def tmp_parse(log):
    data = log.split("\n")
    data.pop(len(data) - 1)
    for i in data:
        i = i.split(",")
        i = [i[1] + ":" + i[2] + ":" + i[3], i[4]]
        try:
            tmp = float(i[1])
        except ValueError:
            tmp = -1.0
        i[1] = tmp
        i = pl.DataFrame({"Time":[i[0]], "Temperature (C)":[tmp]})
        tmp_df.extend(i)

def convert_time(df):
    return df.with_columns(pl.col("Time").str.to_time(format="%H:%M:%S").alias("Time"))


for f in log_files:
    log = ""
    with open(f, 'r') as file:
        log = file.read()
    if log != "":
        log_parse(log, f)
    file.close()

# print(log_df)

for f in tmp_files:
    log = ""
    file = f
    with open(f, 'r') as file:
        log = file.read()
    if log != "":
        tmp_parse(log)
    file.close()

# print(tmp_df)
tmp_df = (tmp_df.with_row_index().filter(pl.col("index").mod(2) == 0).drop("index")) # drop duplicated temperature data

log_df = convert_time(log_df)
tmp_df = convert_time(tmp_df)

df = log_df.join(tmp_df, "Time", "left")
df = df.sort("Time")
df = df.with_columns(pl.col("Temperature (C)").interpolate(method="linear")).drop_nulls()
print(df)
df.write_parquet("data.parquet")


"""
Begin of map output
"""

# config values
PNG_OUTPUT = "gps_lat_long_plot.png"
DPI = 200 # sharp export
FIG_SIZE = (14, 10)
COLOUR_BY = "Elevation (m)"
CMAP = "cool"
BASEMAP = cx.providers.Esri.WorldStreetMap
DOWNSAMPLE = 1


if DOWNSAMPLE > 1:
    print(f"Downsampling by factor {DOWNSAMPLE}...")
    df = df.gather_every(DOWNSAMPLE)

print(f"Working with {len(df)} points...")

# Create LineString for the full track
coords = list(zip(df["Longitude"], df["Latitude"]))
track_line = LineString(coords)

gdf_track = gpd.GeoDataFrame(
    {"mean_value": [df[COLOUR_BY].mean()]},
    geometry=[track_line],
    crs="EPSG:4326"
)

# Points GeoDataFrame for coloured scatter/line
gdf_points = gpd.GeoDataFrame(
    df.select([
        "Time",
        "Satellite Count",
        "Speed Over Ground (knots)",
        "Elevation (m)",
        "Temperature (C)"
    ]).to_pandas(),
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs="EPSG:4326"
)

# Plotting
fig, ax = plt.subplots(figsize=FIG_SIZE)

# Plot coloured track
gdf_points.plot(
    ax=ax,
    column=COLOUR_BY,
    cmap=CMAP,
    linewidth=2.8,
    markersize=8,
    legend=True,
    scheme="Quantiles", # bins for nice legend (not hundreds of entries)
    k=8, # 8 legend classes
    legend_kwds={
        "loc": "upper right",
        "title": COLOUR_BY,
        "title_fontsize": 11,
        "fontsize": 9,
    },
    alpha=0.9,
    zorder=5
)

# Add basemap (caches tiles after first run)
cx.add_basemap(
    ax,
    crs="EPSG:4326",
    source=BASEMAP,
    zoom=13, # auto-adjusts, but 12–14 good for Burlington
    reset_extent=False
)

# Zoom nicely to data and padding
minx, miny, maxx, maxy = gdf_track.total_bounds
ax.set_xlim(minx - 0.015, maxx + 0.015)
ax.set_ylim(miny - 0.01,  maxy + 0.01)

ax.set_title(
    f"GPS Track – {len(df)} points @ 1 Hz\n"
    f"Coloured by {COLOUR_BY} | Lat/Long Plot",
    fontsize=14, pad=15
)

ax.set_axis_off() # clean look

# Tight layout and export
plt.tight_layout()
plt.savefig(PNG_OUTPUT, dpi=DPI, bbox_inches="tight", pad_inches=0.08)
print(f"Map saved → {PNG_OUTPUT}")

plt.show()





"""
Geodetic to ECEF
"""
def geodetic_to_ecef(
    lat_deg: float | pl.Series | np.ndarray,
    lon_deg: float | pl.Series | np.ndarray,
    height_m: float | pl.Series | np.ndarray
) -> tuple[float | pl.Series | np.ndarray, ...]:
    """
    Convert WGS84 geodetic (lat °, lon °, height m) → ECEF X,Y,Z (m).
    Vectorised; works on scalars, arrays, or Polars Series.
    
    Returns: (X, Y, Z)
    """
    # WGS84 ellipsoid parameters
    a = 6378137.0          # semi-major axis (m)
    f = 1.0 / 298.257223563  # flattening
    b = a * (1.0 - f)      # semi-minor axis
    e2 = f * (2.0 - f)     # first eccentricity squared

    # Convert to radians
    lat = np.deg2rad(lat_deg)
    lon = np.deg2rad(lon_deg)

    # Precompute trig
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    sin_lon = np.sin(lon)
    cos_lon = np.cos(lon)

    # Radius of curvature in the prime vertical
    N = a / np.sqrt(1.0 - e2 * sin_lat**2)

    # ECEF coordinates
    X = (N + height_m) * cos_lat * cos_lon
    Y = (N + height_m) * cos_lat * sin_lon
    Z = (N * (1.0 - e2) + height_m) * sin_lat

    return X, Y, Z


lat = df["Latitude"].to_numpy()
lon = df["Longitude"].to_numpy()
hgt = df["Elevation (m)"].to_numpy()

X, Y, Z = geodetic_to_ecef(lat, lon, hgt)

df = df.with_columns(
    pl.Series("X", X),
    pl.Series("Y", Y),
    pl.Series("Z", Z)
)


# Plot constants
COLOUR_BY = "Elevation (m)"
CMAP = "cool"
FIG_SIZE = (12, 10)
ELEV, AZIM = 25, -110 # view angles
PNG_OUTPUT = "gps_track_ecef_3d.png"
DPI = 180

# Extract ECEF arrays
x = df["X"].to_numpy()
y = df["Y"].to_numpy()
z = df["Z"].to_numpy()
colour_values = df[COLOUR_BY].to_numpy()

print(f"Plotting {len(x)} ECEF points...")

# Create figure & 3D axis
fig = plt.figure(figsize=FIG_SIZE)
ax = fig.add_subplot(111, projection='3d')

# Main track line
sc = ax.scatter(
    x, y, z,
    c=colour_values,
    cmap=CMAP,
    s=15, # point size
    alpha=0.85,
    linewidth=0,
    edgecolor='none'
)

# Connect points with a thin line
ax.plot(x, y, z,
        color='gray',
        linewidth=1.2,
        alpha=0.4,
        zorder=1)

# Start & End markers
ax.scatter([x[0]], [y[0]], [z[0]],
           color='lime', s=180, marker='o',
           edgecolor='black', linewidth=1.5,
           label='Start', zorder=10)

ax.scatter([x[-1]], [y[-1]], [z[-1]],
           color='red', s=180, marker='^',
           edgecolor='black', linewidth=1.5,
           label='End', zorder=10)

# Colourbar
norm = plt.Normalize(colour_values.min(), colour_values.max())
sm = cm.ScalarMappable(cmap=CMAP, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, shrink=0.7, aspect=30, pad=0.08)
cbar.set_label(COLOUR_BY, fontsize=11)

# Labels and title
ax.set_xlabel('ECEF X (m)', fontsize=10)
ax.set_ylabel('ECEF Y (m)', fontsize=10)
ax.set_zlabel('ECEF Z (m)', fontsize=10)

ax.set_title(
    f"GPS Track in ECEF Coordinates\n"
    f"{len(x)} points @ 1 Hz | Coloured by {COLOUR_BY}\n"
    f"Arduino + Ultimate GPS Logger",
    fontsize=13, pad=15
)

# Nice view angles
ax.view_init(elev=ELEV, azim=AZIM)

# Equal aspect ratio in 3D
max_range = np.array([x.max()-x.min(), y.max()-y.min(), z.max()-z.min()]).max() / 2.0
mid_x = (x.max() + x.min()) * 0.5
mid_y = (y.max() + y.min()) * 0.5
mid_z = (z.max() + z.min()) * 0.5
ax.set_xlim(mid_x - max_range, mid_x + max_range)
ax.set_ylim(mid_y - max_range, mid_y + max_range)
ax.set_zlim(mid_z - max_range, mid_z + max_range)

# Grid for reference
ax.grid(True, alpha=0.3)

# Legend for start/end points
ax.legend(loc='upper right', fontsize=9)

# Tight layout and save
plt.tight_layout()
plt.savefig(PNG_OUTPUT, dpi=DPI, bbox_inches='tight')
print(f"3D ECEF plot saved → {PNG_OUTPUT}")

plt.show()




"""
Geodetic to East North Up
"""
def add_enu_columns(
    df: pl.DataFrame,
    lat_col: str = "Latitude",
    lon_col: str = "Longitude",
    alt_col: str = "Elevation (m)",
    enu_prefix: str = "enu_"
) -> pl.DataFrame:
    """
    Adds ENU (East, North, Up) coordinates relative to the FIRST point in the DataFrame.
    
    Assumes WGS84 ellipsoid.
    Input df must have at least one valid row with lat/lon/alt.
    
    Returns new DataFrame with columns:
        enu_east_m, enu_north_m, enu_up_m
    """
    if len(df) == 0:
        raise ValueError("DataFrame is empty")

    # Extract reference, first row (can change logic if you prefer median / known point)
    ref = df.row(0) # first row as tuple
    lat0 = ref[df.get_column_index(lat_col)]
    lon0 = ref[df.get_column_index(lon_col)]
    alt0 = ref[df.get_column_index(alt_col)]

    print(f"Using starting point as ENU origin: lat={lat0:.6f}°, lon={lon0:.6f}°, alt={alt0:.2f} m")

    # Reference ECEF
    p_ref = geodetic_to_ecef(lat0, lon0, alt0)#lla_to_ecef(lat0, lon0, alt0)

    # All points to ECEF (vectorized)
    lats = df[lat_col].to_numpy()
    lons = df[lon_col].to_numpy()
    alts = df[alt_col].to_numpy()

    # Quick vectorized ECEF conversion
    lats_rad = np.deg2rad(lats)
    lons_rad = np.deg2rad(lons)
    N = 6378137.0 / np.sqrt(1 - 6.69437999014e-3 * np.sin(lats_rad)**2)
    x = (N + alts) * np.cos(lats_rad) * np.cos(lons_rad)
    y = (N + alts) * np.cos(lats_rad) * np.sin(lons_rad)
    z = (N * (1 - 6.69437999014e-3) + alts) * np.sin(lats_rad)

    # Delta vectors in ECEF
    dx = x - p_ref[0]
    dy = y - p_ref[1]
    dz = z - p_ref[2]

    # Rotation matrix ECEF to ENU at reference point
    sin_lat = np.sin(np.deg2rad(lat0))
    cos_lat = np.cos(np.deg2rad(lat0))
    sin_lon = np.sin(np.deg2rad(lon0))
    cos_lon = np.cos(np.deg2rad(lon0))

    # ENU rotation matrix (rows = east, north, up)
    R = np.array([
        [-sin_lon, cos_lon, 0.0], # East
        [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat], # North
        [ cos_lat * cos_lon, cos_lat * sin_lon, sin_lat] # Up
    ])

    # Apply rotation to each delta vector
    enu = np.column_stack((dx, dy, dz)) @ R.T 

    # Add to Polars
    return df.with_columns([
        pl.Series(f"{enu_prefix}east_m",  enu[:, 0]),
        pl.Series(f"{enu_prefix}north_m", enu[:, 1]),
        pl.Series(f"{enu_prefix}up_m",    enu[:, 2]),
    ])

# Plot constants
COLOUR_BY       = "Elevation (m)"
CMAP           = "cool"
FIG_SIZE       = (12, 10)
ELEV, AZIM     = 25, -110 # view angles
PNG_OUTPUT     = "gps_track_enu_3d.png"
DPI            = 180

df = add_enu_columns(df)

x = df["enu_east_m"].to_numpy()
y = df["enu_north_m"].to_numpy()
z = df["enu_up_m"].to_numpy()
coloUr_values = df[COLOUR_BY].to_numpy()

print(f"Plotting {len(x)} ENU points...")

# Create figure and 3D axis
fig = plt.figure(figsize=FIG_SIZE)
ax = fig.add_subplot(111, projection='3d')

# Main track line
sc = ax.scatter(
    x, y, z,
    c=colour_values,
    cmap=CMAP,
    s=15, # point size
    alpha=0.85,
    linewidth=0,
    edgecolor='none'
)

# Connect points with a thin line (helps see continuity)
ax.plot(x, y, z,
        color='gray',
        linewidth=1.2,
        alpha=0.4,
        zorder=1)

# Start & End markers
ax.scatter([x[0]], [y[0]], [z[0]],
           color='lime', s=180, marker='o',
           edgecolor='black', linewidth=1.5,
           label='Start', zorder=10)

ax.scatter([x[-1]], [y[-1]], [z[-1]],
           color='red', s=180, marker='^',
           edgecolor='black', linewidth=1.5,
           label='End', zorder=10)

# Colourbar
norm = plt.Normalize(colour_values.min(), colour_values.max())
sm = cm.ScalarMappable(cmap=CMAP, norm=norm)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, shrink=0.7, aspect=30, pad=0.08)
cbar.set_label(COLOUR_BY, fontsize=11)

# Labels & title
ax.set_xlabel('East (m)', fontsize=10)
ax.set_ylabel('North (m)', fontsize=10)
ax.set_zlabel('Up (m)', fontsize=10)

ax.set_title(
    f"GPS Track in ENU Coordinates\n"
    f"{len(x)} points @ 1 Hz | Coloured by {COLOUR_BY}\n"
    f"Arduino + Ultimate GPS Logger",
    fontsize=13, pad=15
)

ax.view_init(elev=ELEV, azim=AZIM) # View angles

# Equal aspect ratio in 3D
max_range = np.array([x.max()-x.min(), y.max()-y.min(), z.max()-z.min()]).max() / 2.0
mid_x = (x.max() + x.min()) * 0.5
mid_y = (y.max() + y.min()) * 0.5
mid_z = (z.max() + z.min()) * 0.5
ax.set_xlim(mid_x - max_range, mid_x + max_range)
ax.set_ylim(mid_y - max_range, mid_y + max_range)
ax.set_zlim(z.min(), z.max())

# Grid for reference
ax.grid(True, alpha=0.3)

# Legend for start/end symbol
ax.legend(loc='upper right', fontsize=9)

# Tight layout and save
plt.tight_layout()
plt.savefig(PNG_OUTPUT, dpi=DPI, bbox_inches='tight')
print(f"3D ENU plot saved → {PNG_OUTPUT}")

plt.show()








