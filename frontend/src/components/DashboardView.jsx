import React, { useState, useEffect } from 'react';
import '../styles/DashboardView.css';

const DashboardView = ({ state }) => {
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [lastSync, setLastSync] = useState(null);

  useEffect(() => {
    const fetchAppointments = () => {
      fetch('/api/signin/appointments')
        .then(res => res.ok ? res.json() : null)
        .then(data => {
          if (data) {
            setAppointments(data.appointments || []);
            setDoctors(data.doctors || []);
            setLastSync(data.last_sync);
          }
        })
        .catch(() => {});
    };

    fetchAppointments();
    const interval = setInterval(fetchAppointments, 60000);
    return () => clearInterval(interval);
  }, []);
  if (!state) {
    return (
      <div className="dashboard-loading">
        <div className="spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  const currentPeople = state.current_people || 0;
  const entriestoday = state.entries_today || 0;
  const fps = state.fps || 0;
  const frameNumber = state.frame_number || 0;

  return (
    <div className="dashboard-view">
      <div className="dashboard-container">
        <header className="dashboard-header">
          <div className="header-content">
            <h1>🏥 Clinic Entrance Detector</h1>
            <p className="subtitle">Digital Signin System</p>
          </div>
          <div className="header-stats">
            <div className="stat">
              <span className="stat-label">FPS</span>
              <span className="stat-value">{fps.toFixed(1)}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Frame</span>
              <span className="stat-value">{frameNumber}</span>
            </div>
          </div>
        </header>

        <div className="dashboard-content">
          <section className="status-section">
            <h2>Live Status</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">👥</div>
                <div className="stat-info">
                  <div className="stat-label">Currently Detected</div>
                  <div className="stat-large-value">{currentPeople}</div>
                  <div className="stat-detail">people in view</div>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">📊</div>
                <div className="stat-info">
                  <div className="stat-label">Entries Today</div>
                  <div className="stat-large-value">{entriestoday}</div>
                  <div className="stat-detail">total detections</div>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">⚡</div>
                <div className="stat-info">
                  <div className="stat-label">Processing</div>
                  <div className="stat-large-value">{fps.toFixed(1)}</div>
                  <div className="stat-detail">frames per second</div>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">✅</div>
                <div className="stat-info">
                  <div className="stat-label">System Status</div>
                  <div className="stat-large-value">Ready</div>
                  <div className="stat-detail">all systems operational</div>
                </div>
              </div>
            </div>
          </section>

          <section className="video-section">
            <h2>Live Video Feed</h2>
            <div className="video-container">
              <img
                src="/api/video_feed"
                alt="Live camera feed"
                className="video-feed"
              />
              <div className="video-overlay">
                <span className="live-indicator">● LIVE</span>
              </div>
            </div>
          </section>

          <section className="appointments-section">
            <h2>Programari Azi ({appointments.length})</h2>
            {lastSync && (
              <p className="sync-info">Ultima sincronizare: {new Date(lastSync).toLocaleTimeString('ro-RO')}</p>
            )}
            {doctors.length > 0 && (
              <p className="doctors-info">
                Medici: {doctors.map(d => d.full_name).join(', ')}
              </p>
            )}
            {appointments.length > 0 ? (
              <div className="appointments-list">
                {appointments.map((appt) => (
                  <div key={appt.id} className="appointment-item">
                    <span className="appt-time">{appt.time}</span>
                    <span className="appt-name">{appt.full_name}</span>
                    <span className="appt-doctor">Dr. {doctors.find(d => d.id === appt.medic_id)?.last_name || appt.medic_id}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-appointments">Nicio programare pentru azi</p>
            )}
            <button
              className="btn-refresh"
              onClick={() => {
                fetch('/api/signin/refresh-appointments')
                  .then(res => res.json())
                  .then(() => {
                    fetch('/api/signin/appointments')
                      .then(res => res.json())
                      .then(data => {
                        setAppointments(data.appointments || []);
                        setDoctors(data.doctors || []);
                        setLastSync(data.last_sync);
                      });
                  })
                  .catch(() => {});
              }}
            >
              Refresh Programari
            </button>
          </section>

          <section className="recent-events">
            <h2>Recent Activity</h2>
            {state.event_log && state.event_log.length > 0 ? (
              <div className="events-list">
                {state.event_log.slice(0, 5).map((event, idx) => (
                  <div key={idx} className="event-item">
                    <span className="event-time">
                      {new Date().toLocaleTimeString()}
                    </span>
                    <span className="event-type">{event.event}</span>
                    <span className="event-detail">
                      {event.person_id && `ID: ${event.person_id}`}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-events">No recent events</p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

export default DashboardView;
