import React from 'react';
import '../styles/steps.css';

const CreatingSignin = ({ appointment, phone, loading }) => {
  return (
    <div className="creating-signin">
      <div className="creating-content">
        <h2>Creating Digital Signin</h2>

        <div className="status-steps">
          <div className="step completed">
            <div className="step-icon">✓</div>
            <div className="step-text">
              <p className="step-title">Name Matched</p>
              <p className="step-detail">{appointment?.full_name}</p>
            </div>
          </div>

          <div className="step-connector"></div>

          <div className="step completed">
            <div className="step-icon">✓</div>
            <div className="step-text">
              <p className="step-title">Phone Verified</p>
              <p className="step-detail">{phone}</p>
            </div>
          </div>

          <div className="step-connector"></div>

          <div className="step active">
            <div className="step-icon loading">
              <div className="spinner"></div>
            </div>
            <div className="step-text">
              <p className="step-title">Creating Presentation</p>
              <p className="step-detail">Setting up digital signin...</p>
            </div>
          </div>
        </div>

        <div className="progress-bar">
          <div className="progress-fill"></div>
        </div>

        <p className="loading-message">
          Please wait while we set up the digital signin system...
        </p>
      </div>
    </div>
  );
};

export default CreatingSignin;
