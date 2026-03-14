import React, { useEffect, useRef, useState } from 'react';
import '../styles/steps.css';

const ListeningForName = ({ snapshot, detectedName, loading, error, onNameDetected }) => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef(null);

  useEffect(() => {
    // Initialize Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.lang = 'ro-RO';
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;

      recognitionRef.current.onstart = () => {
        setIsListening(true);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current.onresult = (event) => {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            // Final result - process the name
            setTranscript(transcript);
            onNameDetected(transcript);
          } else {
            interimTranscript += transcript;
          }
        }
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, [onNameDetected]);

  const handleStartListening = () => {
    if (recognitionRef.current && !isListening) {
      setTranscript('');
      recognitionRef.current.start();
    }
  };

  const handleManualInput = () => {
    const name = prompt('Enter patient name:');
    if (name && name.trim()) {
      onNameDetected(name.trim());
    }
  };

  return (
    <div className="listening-for-name">
      <div className="snapshot-container">
        {snapshot ? (
          <img src={snapshot} alt="Patient snapshot" className="snapshot" />
        ) : (
          <div className="snapshot-placeholder">Camera Snapshot</div>
        )}
      </div>

      <div className="listening-content">
        <h2>Listening for patient name...</h2>

        {!detectedName ? (
          <div className="listening-controls">
            <button
              className="btn btn-primary btn-large"
              onClick={handleStartListening}
              disabled={loading || isListening}
            >
              {isListening ? (
                <>
                  <span className="listening-indicator">🎤 Listening...</span>
                </>
              ) : (
                '🎤 Start Listening'
              )}
            </button>

            <button
              className="btn btn-secondary"
              onClick={handleManualInput}
              disabled={loading}
            >
              Type Name Manually
            </button>
          </div>
        ) : (
          <div className="detected-name">
            <p className="label">Detected Name:</p>
            <p className="name-display">{detectedName}</p>
            {loading && <div className="spinner"></div>}
          </div>
        )}

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ListeningForName;
