import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import SigninWorkflow from './components/SigninWorkflow';
import DashboardView from './components/DashboardView';

function App() {
  const [ws, setWs] = useState(null);
  const [dashboardState, setDashboardState] = useState(null);
  const [signinEvent, setSigninEvent] = useState(null);
  const [view, setView] = useState('dashboard'); // 'dashboard' or 'signin'

  useEffect(() => {
    // Connect to WebSocket
    const wsUrl = `ws://${window.location.host}/ws`;
    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      console.log('Connected to detector');
      setWs(websocket);
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setDashboardState(data);

        // When person detected, switch to signin view
        if (data.event_log && data.event_log.length > 0) {
          const latestEvent = data.event_log[0];
          if (latestEvent.event === 'signin_started') {
            setSigninEvent(latestEvent);
            setView('signin');
          }
        }
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('WebSocket closed');
      setTimeout(() => {
        window.location.reload();
      }, 3000);
    };

    return () => {
      if (websocket) websocket.close();
    };
  }, []);

  return (
    <div className="app">
      {view === 'dashboard' && dashboardState && (
        <DashboardView state={dashboardState} />
      )}

      {view === 'signin' && signinEvent && (
        <SigninWorkflow
          event={signinEvent}
          onComplete={() => {
            setView('dashboard');
            setSigninEvent(null);
          }}
        />
      )}
    </div>
  );
}

export default App;
