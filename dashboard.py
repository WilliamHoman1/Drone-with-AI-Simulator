import streamlit as st
import plotly.graph_objects as go
import time

st.set_page_config(page_title="UAV Swarm Dashboard", page_icon="🛸", layout="wide")

# ---------------------------------------------------------------- data source
#
# There is exactly one source of truth here: swarm_api. When it is unreachable
# the dashboard says so and renders empty.
#
# It used to fall back to a generator that invented plausible detections —
# random labels, random confidences, drifting positions — flagged only by a small
# chip in the corner. That is worse than showing nothing: the failure looked
# exactly like a working system, and the labels it invented ('backpack',
# 'truck') were objects that existed nowhere in the simulation.
import requests

EMPTY = {'drones': {}, 'detections': [], 'missions': [],
         'alerts': [], 'scans': [], 'active_targets': 0}

try:
    data = requests.get('http://localhost:8000/state', timeout=2).json()
    data['drones'] = {int(k): v for k, v in data['drones'].items()}
    ros_connected = True
except Exception:
    data = EMPTY
    ros_connected = False

drones = data['drones']
detections = list(data.get('detections', []))
alerts = list(data.get('alerts', []))
missions = list(data.get('missions', []))
scans = list(data.get('scans', []))
investigating = sum(1 for d in drones.values() if d['status'] == 'investigating')

TIER_COLOR = {'high': '#D93025', 'medium': '#C77700', 'low': '#8A8A8A'}
DRONE_COLOR = ['#185FA5', '#0F6E56', '#533AB7']

# ---------------------------------------------------------------- header
head_l, head_r = st.columns([4, 1])
with head_l:
    st.markdown("### 🛸 Autonomous UAV Swarm — Live Operations")
with head_r:
    st.markdown(
        f"<div style='text-align:right;padding-top:8px;'>"
        f"{'🟢 ROS 2 live' if ros_connected else '🔴 No connection'}</div>",
        unsafe_allow_html=True,
    )

if not ros_connected:
    st.error(
        "Cannot reach the swarm API on http://localhost:8000. "
        "Start the stack with `docker compose up`, then reload this page. "
        "Nothing below is live."
    )

# ---------------------------------------------------------------- KPI row
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Drones", f"{len(drones)}/3 active")
k2.metric("Investigating", investigating)
k3.metric("Active Targets", data.get('active_targets', 0))
k4.metric("Cleared", len(scans))
k5.metric("High-Priority Alerts", len(alerts), delta=None)

if alerts:
    a = alerts[0]
    st.error(
        f"🚨 **{a['label'].upper()}** — Drone {a['detected_by']} · "
        f"({a['x']}, {a['y']}) · {a['time']}   ·   {len(alerts)} alert(s) this session"
    )

st.divider()

# ---------------------------------------------------------------- map + feed
left, right = st.columns([3, 2])

with left:
    fig = go.Figure()
    # Must match SearchPattern.SearchWidth / SearchDepth / SectorCount in Unity.
    SEARCH_W, SEARCH_D, SECTORS = 60, 30, 3
    SECTOR_W = SEARCH_W / SECTORS

    for i in range(SECTORS):
        x0, x1 = i * SECTOR_W, (i + 1) * SECTOR_W
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0, x0], y=[0, 0, SEARCH_D, SEARCH_D, 0],
            fill='toself', mode='lines',
            fillcolor=f"rgba{tuple(int(DRONE_COLOR[i][j:j+2], 16) for j in (1, 3, 5)) + (0.06,)}",
            line=dict(color=DRONE_COLOR[i], width=1), hoverinfo='skip', showlegend=False,
        ))
        fig.add_annotation(
            x=(x0 + x1) / 2, y=SEARCH_D - 1.5, showarrow=False,
            text=f"SECTOR {'ABC'[i]}",
            font=dict(size=11, color=DRONE_COLOR[i]),
        )
    for did, d in drones.items():
        fig.add_trace(go.Scatter(
            x=[d['x']], y=[d['y']], mode='markers+text',
            marker=dict(size=18, color=DRONE_COLOR[did - 1], symbol='diamond',
                        line=dict(width=2, color='white')),
            text=[f"D{did}"], textposition='top center',
            name=f"Drone {did}", hovertext=d['status'], hoverinfo='text+name',
        ))
    for det in detections[:6]:
        fig.add_trace(go.Scatter(
            x=[det['x']], y=[det['y']], mode='markers',
            marker=dict(size=12, color=TIER_COLOR.get(det.get('tier', 'low'), '#8A8A8A'),
                        symbol='x', line=dict(width=1)),
            hovertext=f"{det['label']} ({det['confidence']})", hoverinfo='text', showlegend=False,
        ))
    fig.update_layout(
        height=420, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(range=[-3, SEARCH_W + 3], showgrid=True,
                   gridcolor='rgba(0,0,0,0.05)', zeroline=False),
        yaxis=dict(range=[-3, SEARCH_D + 3], showgrid=True,
                   gridcolor='rgba(0,0,0,0.05)', zeroline=False,
                   scaleanchor='x', scaleratio=1),
        plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation='h', y=-0.12),
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    tab_feed, tab_class, tab_missions = st.tabs(["Detections", "Cleared", "Missions"])

    with tab_feed:
        if not detections:
            st.caption("Waiting for detections…")
        for det in detections[:10]:
            tier = det.get('tier', 'low')
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"border-left:3px solid {TIER_COLOR.get(tier, '#8A8A8A')};"
                f"padding:4px 10px;margin-bottom:4px;background:rgba(0,0,0,0.02);'>"
                f"<span><b>{det['label']}</b> "
                f"<span style='color:{TIER_COLOR.get(tier, '#8A8A8A')};font-size:11px;'>"
                f"{tier.upper()}</span><br>"
                f"<span style='color:gray;font-size:12px;'>Drone {det['drone']} · "
                f"{det['confidence']} conf</span></span>"
                f"<span style='color:gray;font-size:12px;'>{det['time']}</span></div>",
                unsafe_allow_html=True,
            )

    with tab_class:
        if not scans:
            st.caption("No contacts cleared yet — drones scan on arrival.")
        for s in scans[:10]:
            c = TIER_COLOR.get(s.get('tier', 'low'), '#8A8A8A')
            st.markdown(
                f"<div style='border-left:3px solid {c};padding:6px 10px;"
                f"margin-bottom:4px;background:rgba(0,0,0,0.02);'>"
                f"<b style='color:{c};'>{s['result']}</b><br>"
                f"<span style='color:gray;font-size:12px;'>Drone {s['drone']} · "
                f"({s['x']}, {s['y']}) · {s['time']}</span></div>",
                unsafe_allow_html=True,
            )

    with tab_missions:
        if not missions:
            st.caption("No missions yet…")
        for m in missions[:8]:
            st.markdown(
                f"<div style='padding:4px 10px;margin-bottom:4px;"
                f"background:rgba(0,0,0,0.02);border-radius:3px;'>"
                f"<span style='color:gray;font-size:12px;'>{m['time']} · Drone {m['drone']}</span><br>"
                f"<span style='font-size:13px;'>{m['mission']}</span></div>",
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------- refresh
time.sleep(2)
st.rerun()
