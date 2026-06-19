import streamlit as st
import plotly.graph_objects as go
import json
import time
import random

# Page config
st.set_page_config(
    page_title="UAV Swarm Dashboard",
    page_icon="🛸",
    layout="wide"
)

st.title("🛸 Autonomous UAV Swarm — Live Operations")
st.caption("Multi-agent drone system with LLM mission planning")

# Initialize drone state
if 'drones' not in st.session_state:
    st.session_state.drones = {
        1: {'x': 0, 'y': 0, 'status': 'patrolling', 'zone': 'Northwest', 'detections': []},
        2: {'x': 20, 'y': 0, 'status': 'patrolling', 'zone': 'Northeast', 'detections': []},
        3: {'x': 10, 'y': 20, 'status': 'patrolling', 'zone': 'South', 'detections': []}
    }

if 'detection_log' not in st.session_state:
    st.session_state.detection_log = []

if 'mission_log' not in st.session_state:
    st.session_state.mission_log = []

# Simulate drone movement
def update_drones():
    targets = {
        1: [[0,0],[10,0],[10,10],[0,10]],
        2: [[20,0],[30,0],[30,10],[20,10]],
        3: [[10,20],[20,20],[20,30],[10,30]]
    }
    
    for drone_id, drone in st.session_state.drones.items():
        zone_waypoints = targets[drone_id]
        target = random.choice(zone_waypoints)
        drone['x'] += (target[0] - drone['x']) * 0.15
        drone['y'] += (target[1] - drone['y']) * 0.15

        # Random detection event
        if random.random() < 0.1:
            labels = ['person', 'vehicle', 'truck', 'car']
            detection = {
                'drone': drone_id,
                'label': random.choice(labels),
                'confidence': round(random.uniform(0.7, 0.99), 2),
                'time': time.strftime('%H:%M:%S'),
                'x': round(drone['x'], 1),
                'y': round(drone['y'], 1)
            }
            st.session_state.detection_log.insert(0, detection)
            drone['detections'].append(detection)
            drone['status'] = 'investigating'
            st.session_state.mission_log.insert(0, {
                'time': time.strftime('%H:%M:%S'),
                'drone': drone_id,
                'mission': f"Investigate {detection['label']} at ({detection['x']}, {detection['y']})"
            })
        else:
            drone['status'] = 'patrolling'

    # Keep logs short
    st.session_state.detection_log = st.session_state.detection_log[:20]
    st.session_state.mission_log = st.session_state.mission_log[:10]

# Top metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Drones Active", "3/3")
with col2:
    st.metric("Total Detections", len(st.session_state.detection_log))
with col3:
    investigating = sum(1 for d in st.session_state.drones.values() if d['status'] == 'investigating')
    st.metric("Investigating", investigating)
with col4:
    st.metric("Mission Planner", "🟢 Online")

st.divider()

# Main layout
left, right = st.columns([2, 1])

with left:
    st.subheader("Live Map")
    update_drones()

    fig = go.Figure()

    # Draw patrol zones
    zone_colors = ['rgba(25,90,165,0.1)', 'rgba(15,110,86,0.1)', 'rgba(83,58,183,0.1)']
    zone_borders = ['#185FA5', '#0F6E56', '#533AB7']
    zones = [
        dict(x=[0,10,10,0,0], y=[0,0,10,10,0]),
        dict(x=[20,30,30,20,20], y=[0,0,10,10,0]),
        dict(x=[10,20,20,10,10], y=[20,20,30,30,20])
    ]
    zone_names = ['Drone 1 — Northwest', 'Drone 2 — Northeast', 'Drone 3 — South']

    for i, zone in enumerate(zones):
        fig.add_trace(go.Scatter(
            x=zone['x'], y=zone['y'],
            fill='toself',
            fillcolor=zone_colors[i],
            line=dict(color=zone_borders[i], width=2),
            name=zone_names[i],
            mode='lines'
        ))

    # Draw drones
    colors = ['#185FA5', '#0F6E56', '#533AB7']
    symbols = ['diamond', 'diamond', 'diamond']
    for drone_id, drone in st.session_state.drones.items():
        fig.add_trace(go.Scatter(
            x=[drone['x']], y=[drone['y']],
            mode='markers+text',
            marker=dict(size=16, color=colors[drone_id-1], symbol='diamond'),
            text=[f'D{drone_id}'],
            textposition='top center',
            name=f'Drone {drone_id} ({drone["status"]})'
        ))

    # Draw detections
    for det in st.session_state.detection_log[:5]:
        fig.add_trace(go.Scatter(
            x=[det['x']], y=[det['y']],
            mode='markers',
            marker=dict(size=10, color='red', symbol='x'),
            name=f'{det["label"]} ({det["confidence"]})',
            showlegend=False
        ))

    fig.update_layout(
        height=450,
        xaxis=dict(range=[-5, 45], title='X Position'),
        yaxis=dict(range=[-5, 40], title='Y Position'),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor='rgba(0,0,0,0)'
    )

    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Detection Log")
    if st.session_state.detection_log:
        for det in st.session_state.detection_log[:8]:
            color = '#185FA5' if det['drone'] == 1 else '#0F6E56' if det['drone'] == 2 else '#533AB7'
            st.markdown(f"""
            <div style='border-left: 3px solid {color}; padding: 6px 10px; margin-bottom: 6px; background: rgba(0,0,0,0.02); border-radius: 4px;'>
                <span style='font-size:12px; color:gray;'>{det['time']} · Drone {det['drone']}</span><br>
                <span style='font-weight:500;'>{det['label']}</span> 
                <span style='color:gray;'>· {det['confidence']} conf · ({det['x']}, {det['y']})</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No detections yet...")

    st.subheader("Mission Log")
    if st.session_state.mission_log:
        for m in st.session_state.mission_log[:5]:
            st.markdown(f"""
            <div style='padding: 6px 10px; margin-bottom: 6px; background: rgba(0,0,0,0.02); border-radius: 4px;'>
                <span style='font-size:12px; color:gray;'>{m['time']} · Drone {m['drone']}</span><br>
                <span style='font-size:13px;'>{m['mission']}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No missions yet...")

# Auto refresh
time.sleep(0.5)
st.rerun()