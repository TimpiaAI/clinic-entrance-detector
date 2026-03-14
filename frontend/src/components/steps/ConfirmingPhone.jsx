import React, { useState } from 'react';
import '../styles/steps.css';

const ConfirmingPhone = ({ appointment, loading, error, onConfirm }) => {
  const [phone, setPhone] = useState('');
  const [cnp, setCnp] = useState('');
  const [inputError, setInputError] = useState('');
  const [cnpInfo, setCnpInfo] = useState(null);
  const [validatingCnp, setValidatingCnp] = useState(false);

  const validatePhone = (phoneNumber) => {
    const cleaned = phoneNumber.replace(/\D/g, '');
    return cleaned.length >= 10;
  };

  const handlePhoneChange = (e) => {
    setPhone(e.target.value);
    setInputError('');
  };

  const handleCnpChange = async (e) => {
    const value = e.target.value.replace(/\D/g, '');
    setCnp(value);
    setInputError('');
    setCnpInfo(null);

    if (value.length === 13) {
      setValidatingCnp(true);
      try {
        const res = await fetch('/api/signin/validate-cnp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cnp: value }),
        });
        const data = await res.json();
        if (data.valid) {
          setCnpInfo(data);
        } else {
          setInputError('CNP invalid - verificati cifrele');
        }
      } catch {
        // Validation endpoint not available - skip
      }
      setValidatingCnp(false);
    }
  };

  const handleConfirm = () => {
    if (!validatePhone(phone)) {
      setInputError('Introduceti un numar de telefon valid (10+ cifre)');
      return;
    }
    if (cnp.length > 0 && cnp.length !== 13) {
      setInputError('CNP-ul trebuie sa aiba 13 cifre');
      return;
    }
    onConfirm(appointment.appointment_id, phone, cnp || undefined);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading && phone.trim()) {
      handleConfirm();
    }
  };

  return (
    <div className="confirming-phone">
      <div className="appointment-summary">
        <h2>Confirmare Programare</h2>
        <div className="appointment-card">
          <div className="patient-info">
            <span className="label">Pacient:</span>
            <span className="value">{appointment.full_name}</span>
          </div>
          <div className="appointment-info">
            <span className="label">Ora:</span>
            <span className="value">{appointment.time}</span>
          </div>
          <div className="appointment-info">
            <span className="label">Data:</span>
            <span className="value">{appointment.appointment_at}</span>
          </div>
        </div>
      </div>

      <div className="phone-input-section">
        <label htmlFor="cnp" className="input-label">
          CNP Pacient
        </label>
        <div className="phone-input-wrapper">
          <input
            id="cnp"
            type="text"
            inputMode="numeric"
            className={`phone-input ${cnp.length === 13 && !cnpInfo ? 'error' : ''}`}
            placeholder="1234567890123"
            value={cnp}
            onChange={handleCnpChange}
            onKeyPress={handleKeyPress}
            disabled={loading}
            maxLength={13}
            autoFocus
          />
          {cnp && (
            <span className="phone-format-hint">
              {cnp.length}/13 cifre
            </span>
          )}
        </div>
        {cnpInfo && (
          <div className="cnp-routing-info">
            <span className="routing-gender">{cnpInfo.gender === 'M' ? 'Barbat' : 'Femeie'}</span>
            <span className="routing-arrow">&rarr;</span>
            <span className="routing-doctor">Dr. {cnpInfo.doctor_name}</span>
          </div>
        )}
        {validatingCnp && <p className="validating-text">Se verifica CNP...</p>}
      </div>

      <div className="phone-input-section">
        <label htmlFor="phone" className="input-label">
          Numar Telefon Pacient
        </label>
        <div className="phone-input-wrapper">
          <input
            id="phone"
            type="tel"
            className={`phone-input ${inputError && !phone ? 'error' : ''}`}
            placeholder="07XX XXX XXXX"
            value={phone}
            onChange={handlePhoneChange}
            onKeyPress={handleKeyPress}
            disabled={loading}
          />
          {phone && (
            <span className="phone-format-hint">
              {phone.replace(/\D/g, '').length} cifre
            </span>
          )}
        </div>
        {inputError && <p className="input-error">{inputError}</p>}
      </div>

      {error && (
        <div className="error-message">
          <span className="error-icon">!</span>
          <span>{error}</span>
        </div>
      )}

      <div className="action-buttons">
        <button
          className="btn btn-primary btn-large"
          onClick={handleConfirm}
          disabled={loading || !phone.trim()}
        >
          {loading ? (
            <>
              <span className="spinner-small"></span>
              Se creeaza...
            </>
          ) : (
            'Confirma'
          )}
        </button>
      </div>
    </div>
  );
};

export default ConfirmingPhone;
