import React, { useState } from 'react';
import '../styles/steps.css';

const SelectingMatch = ({ detectedName, fuzzyMatches, onSelectMatch }) => {
  const [selectedId, setSelectedId] = useState(null);

  const handleSelect = (appointmentId) => {
    setSelectedId(appointmentId);
    setTimeout(() => {
      onSelectMatch(appointmentId);
    }, 300);
  };

  const getScoreColor = (score) => {
    if (score >= 95) return '#27ae60'; // green
    if (score >= 85) return '#f39c12'; // orange
    return '#e74c3c'; // red
  };

  const getScoreLabel = (score) => {
    if (score >= 95) return '✅ Excellent Match';
    if (score >= 85) return '⚠️ Good Match';
    return '❓ Possible Match';
  };

  return (
    <div className="selecting-match">
      <div className="header">
        <h2>Select Matching Appointment</h2>
        <p className="subtitle">Detected: <span className="detected-name">{detectedName}</span></p>
      </div>

      {fuzzyMatches.length === 0 ? (
        <div className="no-matches">
          <p>❌ No matches found</p>
          <p className="help-text">Please verify the name or add patient manually</p>
        </div>
      ) : (
        <div className="matches-list">
          {fuzzyMatches.map((match, index) => (
            <div
              key={match.appointment_id}
              className={`match-card ${selectedId === match.appointment_id ? 'selected' : ''}`}
              onClick={() => handleSelect(match.appointment_id)}
              style={{ cursor: 'pointer' }}
            >
              <div className="match-rank">#{index + 1}</div>

              <div className="match-info">
                <div className="patient-name">{match.full_name}</div>
                <div className="appointment-details">
                  <span className="appointment-time">📅 {match.time}</span>
                  <span className="appointment-date">{match.appointment_at}</span>
                </div>
              </div>

              <div className="match-score">
                <div
                  className="score-bar"
                  style={{
                    width: `${match.score}%`,
                    backgroundColor: getScoreColor(match.score),
                  }}
                ></div>
                <div className="score-text">
                  <span className="score-number">{match.score.toFixed(1)}%</span>
                  <span className="score-label">{getScoreLabel(match.score)}</span>
                </div>
              </div>

              {selectedId === match.appointment_id && (
                <div className="selection-indicator">✓ Selected</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SelectingMatch;
