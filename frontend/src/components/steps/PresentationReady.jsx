import React, { useState } from 'react';
import '../styles/steps.css';

const PresentationReady = ({ presentationId, appointment, onDone }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyId = () => {
    navigator.clipboard.writeText(presentationId.toString());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDone = () => {
    onDone();
  };

  return (
    <div className="presentation-ready">
      <div className="success-header">
        <div className="success-icon">✅</div>
        <h2>Digital Signin Created</h2>
      </div>

      <div className="patient-info-summary">
        <div className="info-row">
          <span className="label">Patient:</span>
          <span className="value">{appointment?.full_name}</span>
        </div>
        <div className="info-row">
          <span className="label">Appointment:</span>
          <span className="value">{appointment?.time}</span>
        </div>
      </div>

      <div className="presentation-id-section">
        <p className="presentation-label">Show patient this number:</p>

        <div className="presentation-id-display">
          <div className="id-number">{presentationId}</div>
          <button
            className="btn btn-copy"
            onClick={handleCopyId}
            title="Copy to clipboard"
          >
            {copied ? '✓ Copied' : '📋 Copy'}
          </button>
        </div>

        <p className="presentation-instruction">
          Patient enters this number on the tablet to sign and complete the check-in
        </p>
      </div>

      <div className="next-steps">
        <h3>Next Steps:</h3>
        <ol>
          <li>Show patient the presentation ID: <strong>{presentationId}</strong></li>
          <li>Direct patient to tablet for digital signature</li>
          <li>System will confirm when signature is complete</li>
        </ol>
      </div>

      <div className="action-buttons">
        <button
          className="btn btn-primary btn-large"
          onClick={handleDone}
        >
          ✓ Done - Return to Dashboard
        </button>
      </div>

      <div className="info-box">
        <p>
          💡 <strong>Tip:</strong> Keep this screen visible or note down the presentation ID
          ({presentationId}) for your records.
        </p>
      </div>
    </div>
  );
};

export default PresentationReady;
