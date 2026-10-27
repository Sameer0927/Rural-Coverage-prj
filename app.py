# Coverage Dead-Zone Heatmap Tool  (SW-34 + auto-suggest tower spot)
# Run with:  streamlit run app.py

import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# ---------- 1. SETTINGS (you can change these numbers) ----------
SIZE_KM = 10          # our map is 10 km x 10 km
GRID = 100            # map is split into 100 x 100 small squares
THRESHOLD = -100      # signal at or above this (in dBm) = "has network"
LOSS_AT_1KM = 110     # how much signal is lost in the first 1 km (dB)
EXPONENT = 3.5        # bigger number = signal fades faster (rural ~3.5)

# ---------- 2. FAKE VILLAGES (same every run because of seed 7) ----------
rng = np.random.default_rng(7)
VILLAGES = rng.uniform(0.5, 9.5, size=(18, 2))   # 18 villages: (x, y) in km

# ---------- 3. GRID OF POINTS FOR THE HEATMAP ----------
xs = np.linspace(0, SIZE_KM, GRID)
ys = np.linspace(0, SIZE_KM, GRID)
GX, GY = np.meshgrid(xs, ys)


# ---------- 4. THE SCIENCE PART ----------
def signal_from_tower(tx, ty, power_dbm, x, y):
    """Signal strength (dBm) at point(s) x,y from ONE tower at (tx,ty)."""
    d = np.sqrt((x - tx) ** 2 + (y - ty) ** 2)   # distance in km
    d = np.maximum(d, 0.05)                      # avoid log(0)
    return power_dbm - (LOSS_AT_1KM + 10 * EXPONENT * np.log10(d))


def best_signal(towers, x, y):
    """At each point, take the strongest signal among all towers."""
    if len(towers) == 0:
        return np.full(np.shape(x), -200.0)
    all_signals = [signal_from_tower(tx, ty, p, x, y) for tx, ty, p in towers]
    return np.max(all_signals, axis=0)


def villages_covered(towers):
    sig = best_signal(towers, VILLAGES[:, 0], VILLAGES[:, 1])
    return sig >= THRESHOLD          # list of True/False, one per village


def suggest_best_spot(towers, power):
    """Try many spots for ONE more tower, return the best one."""
    best = None
    for cx in np.linspace(0.25, 9.75, 20):
        for cy in np.linspace(0.25, 9.75, 20):
            test = list(towers) + [(cx, cy, power)]
            score = int(villages_covered(test).sum())
            if best is None or score > best[2]:
                best = (float(cx), float(cy), score)
    return best


# ---------- 5. THE WEBPAGE ----------
st.set_page_config(page_title="Rural Coverage Mapper", layout="wide")
st.title("📡 Rural Coverage Dead-Zone Mapper")
st.write("Move the towers. Green = good signal, red = dead zone. "
         "Then ask the app where the NEXT tower should go.")

st.sidebar.header("Towers")
n_towers = st.sidebar.slider("How many towers?", 1, 4, 1)

default_pos = [(2.5, 2.5), (7.5, 7.5), (2.5, 7.5), (7.5, 2.5)]
towers = []
for i in range(n_towers):
    st.sidebar.subheader(f"Tower {i + 1}")
    tx = st.sidebar.slider("x (km)", 0.0, 10.0, default_pos[i][0], 0.1, key=f"x{i}")
    ty = st.sidebar.slider("y (km)", 0.0, 10.0, default_pos[i][1], 0.1, key=f"y{i}")
    tp = st.sidebar.slider("power (dBm)", 20, 46, 30, key=f"p{i}")
    towers.append((tx, ty, tp))

st.sidebar.header("Smart suggestion")
new_power = st.sidebar.slider("Power of the NEW tower (dBm)", 20, 46, 30, key="newp")
if st.sidebar.button("🔍 Find best spot for one more tower"):
    bx, by, bscore = suggest_best_spot(towers, new_power)
    st.session_state["suggestion"] = (tuple(towers), new_power, bx, by, bscore)

# show the suggestion only if towers have not changed since we computed it
suggestion = None
saved = st.session_state.get("suggestion")
if saved and saved[0] == tuple(towers) and saved[1] == new_power:
    suggestion = saved

# ---------- 6. DRAW THE MAP ----------
signal_map = best_signal(towers, GX, GY)
covered = villages_covered(towers)

fig, ax = plt.subplots(figsize=(8, 7))
img = ax.imshow(signal_map, extent=[0, SIZE_KM, 0, SIZE_KM], origin="lower",
                cmap="RdYlGn", vmin=-130, vmax=-60)
ax.contour(GX, GY, signal_map, levels=[THRESHOLD], colors="black", linewidths=1.5)
fig.colorbar(img, ax=ax, label="Signal strength (dBm)")

ax.scatter(VILLAGES[covered, 0], VILLAGES[covered, 1], c="white",
           edgecolors="black", s=70, label="Village with signal")
ax.scatter(VILLAGES[~covered, 0], VILLAGES[~covered, 1], c="red",
           marker="X", edgecolors="black", s=110, label="Village WITHOUT signal")
for tx, ty, tp in towers:
    ax.scatter(tx, ty, c="blue", marker="^", s=250, edgecolors="white")
if suggestion:
    ax.scatter(suggestion[2], suggestion[3], c="gold", marker="*", s=500,
               edgecolors="black", label="Suggested new tower")
ax.set_xlabel("km")
ax.set_ylabel("km")
ax.legend(loc="upper right", fontsize=8)

left, right = st.columns([2, 1])
with left:
    st.pyplot(fig)
with right:
    st.metric("Villages with signal", f"{int(covered.sum())} / {len(VILLAGES)}")
    st.metric("Coverage %", f"{covered.mean() * 100:.0f}%")
    st.metric("Map area covered", f"{(signal_map >= THRESHOLD).mean() * 100:.0f}%")
    if suggestion:
        st.success(f"⭐ Best spot for a new tower: x={suggestion[2]:.1f} km, "
                   f"y={suggestion[3]:.1f} km. Villages covered would become "
                   f"{suggestion[4]} / {len(VILLAGES)}.")
        st.info("Set Tower N+1 to this x and y (and increase the tower count) to see it.")
