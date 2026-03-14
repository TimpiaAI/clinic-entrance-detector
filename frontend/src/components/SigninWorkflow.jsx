import React, { useState, useEffect, useRef } from 'react';
import ListeningForName from './steps/ListeningForName';
import SelectingMatch from './steps/SelectingMatch';
import ConfirmingPhone from './steps/ConfirmingPhone';
import CreatingSignin from './steps/CreatingSignin';
import PresentationReady from './steps/PresentationReady';
import '../styles/SigninWorkflow.css';

const SigninWorkflow = ({ event, onComplete }) => {
  const [step, setStep] = useState('listening'); // listening → selecting → phone → creating → presentation
  const [personId, setPersonId] = useState(event.person_id);
  const [snapshot, setSnapshot] = useState(event.snapshot);
  const [detectedName, setDetectedName] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [fuzzyMatches, setFuzzyMatches] = useState([]);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [phone, setPhone] = useState('');
  const [presentationId, setPresentationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Step 1: Listening for name from Deepgram
  const handleNameDetected = async (name) => {
    setLoading(true);
    setError(null);
    setDetectedName(name);

    try {
      const response = await fetch('/api/signin/detect-name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          person_id: personId,
          detected_name: name
        })
      });

      if (!response.ok) throw new Error('Failed to detect name');
      const data = await response.json();

      setSessionId(data.session_id);
      setFuzzyMatches(data.fuzzy_matches);

      if (data.fuzzy_matches.length > 0) {
        setStep('selecting');
      } else {
        setError('No matches found. Please try again or enter manually.');
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Selecting match and entering phone + CNP
  const handlePhoneConfirm = async (appointmentId, phoneNumber, cnp) => {
    setLoading(true);
    setError(null);

    try {
      const body = {
        person_id: personId,
        session_id: sessionId,
        appointment_id: appointmentId,
        phone: phoneNumber,
      };
      if (cnp) body.cnp = cnp;

      const response = await fetch('/api/signin/confirm-appointment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (!response.ok) throw new Error('Failed to confirm appointment');
      const data = await response.json();

      setSelectedAppointment(data.confirmed_appointment);
      setPhone(phoneNumber);
      setStep('creating');

      // Auto-create signin after confirmation
      setTimeout(() => createSignin(sessionId), 1000);
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Create signin
  const createSignin = async (sid) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/signin/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          person_id: personId,
          session_id: sid
        })
      });

      if (!response.ok) throw new Error('Failed to create signin');
      const data = await response.json();

      setPresentationId(data.presentation_id);
      setStep('presentation');
    } catch (err) {
      setError(`Error: ${err.message}`);
      setStep('phone');
    } finally {
      setLoading(false);
    }
  };

  // Step 4: Show presentation ID
  const handleDone = () => {
    onComplete();
  };

  return (
    <div className="signin-workflow">
      {step === 'listening' && (
        <ListeningForName
          snapshot={snapshot}
          detectedName={detectedName}
          loading={loading}
          error={error}
          onNameDetected={handleNameDetected}
        />
      )}

      {step === 'selecting' && (
        <SelectingMatch
          detectedName={detectedName}
          fuzzyMatches={fuzzyMatches}
          onSelectMatch={(appointmentId) => {
            setSelectedAppointment(
              fuzzyMatches.find(m => m.appointment_id === appointmentId)
            );
            setStep('phone');
          }}
        />
      )}

      {step === 'phone' && (
        <ConfirmingPhone
          appointment={selectedAppointment}
          loading={loading}
          error={error}
          onConfirm={handlePhoneConfirm}
        />
      )}

      {step === 'creating' && (
        <CreatingSignin
          appointment={selectedAppointment}
          phone={phone}
          loading={true}
        />
      )}

      {step === 'presentation' && (
        <PresentationReady
          presentationId={presentationId}
          appointment={selectedAppointment}
          onDone={handleDone}
        />
      )}
    </div>
  );
};

export default SigninWorkflow;
