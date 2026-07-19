import streamlit as st
import plotly.graph_objects as go
import time
import sys
import os

st.set_page_config(
    page_title="UAV Swarm Dashboard",
    page_icon="🛸",
    layout="wide"
)

st.title("🛸 Autonomous UAV Swarm — Live Operations")
st.caption("Multi-agent drone system with LLM mission planning")

# Try to connect to ROS bridge
import requests
try:
    response = requests.get('http://localhost:8000/state', timeout=2)
    data = response.json()
    # Convert lists back to expected format
    data['drones'] = {int(k): v for k, v in data['drones'].items()}
    ros_connected = True
except Exception as e:
    ros_connected = False
    
    # Fall back to simulated data
    import random
    if 'drones' not in st.session_state:
        st.session_state.drones = {
            1: {'x': 0.0, 'y': 0.0, 'status': 'patrolling'},
            2: {'x': 20.0, 'y': 0.0, 'status': 'patrolling'},
            3: {'x': 10.0, 'y': 20.0, 'status': 'patrolling'}
        }
    if 'detections' not in st.session_state:
        st.session_state.detections = []
    if 'missions' not in st.session_state:
        st.session_state.missions = []

    # Simulate movement
    for drone_id, drone in st.session_state.drones.items():
        drone['x'] += random.uniform(-0.5, 0.5)
        drone['y'] += random.uniform(-0.5, 0.5)
        if random.random() < 0.1:
            labels = ['person', 'vehicle', 'truck', 'car']
            st.session_state.detections.insert(0, {
                'drone': drone_id,
                'label': random.choice(labels),
                'confidence': round(random.uniform(0.7, 0.99), 2),
                'time': time.strftime('%H:%M:%S'),
                'x': round(drone['x'], 1),
                'y': round(drone['y'], 1)
            })
    st.session_state.detections = st.session_state.detections[:20]

    data = {
        'drones': st.session_state.drones,
        'detections': st.session_state.detections,
        'missions': st.session_state.missions,
        'active_targets': 0
    }

# Connection status
if ros_connected:
    st.success('🟢 Connected to ROS 2 swarm')
else:
    st.warning('🟡 ROS 2 unavailable — showing simulated data')

# Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Drones Active", "3/3")
with col2:
    st.metric("Total Detections", len(list(data['detections'])))
with col3:
    investigating = sum(1 for d in data['drones'].values() if d['status'] == 'investigating')
    st.metric("Investigating", investigating)
with col4:
    st.metric("Active Targets", data.get('active_targets', 0))

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("Live Map")
    fig = go.Figure()

    # Patrol zones
    zone_colors = ['rgba(25,90,165,0.1)', 'rgba(15,110,86,0.1)', 'rgba(83,58,183,0.1)']
    zone_borders = ['#185FA5', '#0F6E56', '#533AB7']
    zones = [
        dict(x=[0,10,10,0,0], y=[0,0,10,10,0]),
        dict(x=[20,30,30,20,20], y=[0,0,10,10,0]),
        dict(x=[10,20,20,10,10], y=[20,20,30,30,20])
    ]
    zone_names = ['Drone 1 — NW', 'Drone 2 — NE', 'Drone 3 — South']

    for i, zone in enumerate(zones):
        fig.add_trace(go.Scatter(
            x=zone['x'], y=zone['y'],
            fill='toself',
            fillcolor=zone_colors[i],
            line=dict(color=zone_borders[i], width=2),
            name=zone_names[i],
            mode='lines'
        ))

    # Drones
    colors = ['#185FA5', '#0F6E56', '#533AB7']
    for drone_id, drone in data['drones'].items():
        fig.add_trace(go.Scatter(
            x=[drone['x']], y=[drone['y']],
            mode='markers+text',
            marker=dict(size=16, color=colors[drone_id-1], symbol='diamond'),
            text=[f'D{drone_id}'],
            textposition='top center',
            name=f'Drone {drone_id} ({drone["status"]})'
        ))

    # Detections
    for det in list(data['detections'])[:5]:
        fig.add_trace(go.Scatter(
            x=[det['x']], y=[det['y']],
            mode='markers',
            marker=dict(size=10, color='red', symbol='x'),
            showlegend=False
        ))

    fig.update_layout(
        height=450,
        xaxis=dict(range=[-5, 45], title='X'),
        yaxis=dict(range=[-5, 40], title='Y'),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Detection Log")
    detections = list(data['detections'])
    if detections:
        for det in detections[:8]:
            color = ['#185FA5', '#0F6E56', '#533AB7'][det['drone']-1]
            st.markdown(f"""
            <div style='border-left:3px solid {color}; padding:6px 10px; margin-bottom:6px; border-radius:4px;'>
                <span style='font-size:12px; color:gray;'>{det['time']} · Drone {det['drone']}</span><br>
                <span style='font-weight:500;'>{det['label']}</span>
                <span style='color:gray;'> · {det['confidence']} conf</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("Waiting for detections...")

    st.subheader("Mission Log")
    missions = list(data['missions'])
    if missions:
        for m in missions[:5]:
            st.markdown(f"""
            <div style='padding:6px 10px; margin-bottom:6px; background:rgba(0,0,0,0.02); border-radius:4px;'>
                <span style='font-size:12px; color:gray;'>{m['time']} · Drone {m['drone']}</span><br>
                <span style='font-size:13px;'>{m['mission']}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No missions yet...")



# Auto refresh
time.sleep(1)
st.rerun()