/**
 * Romanian UI string constants.
 *
 * All user-facing text is centralized here. Technical terms
 * (FPS, Webhook, ID) are kept as-is since they are universal.
 */

export const RO = {
  // Header
  APP_TITLE: 'Detector Intrare Clinica',

  // Status panel labels
  FPS: 'FPS',
  ACTIVE_TRACKS: 'Persoane active',
  ENTRIES_TODAY: 'Intrari astazi',
  UPTIME: 'Timp functionare',
  WEBHOOK_STATUS: 'Webhook',
  DETECTOR_STATUS: 'Detector',
  WAKE_LOCK: 'Blocare ecran',

  // Status values
  RUNNING: 'Activ',
  STOPPED: 'Oprit',
  CONNECTED: 'Conectat',
  DISCONNECTED: 'Deconectat',
  HEALTHY: 'Functional',
  ERROR: 'Eroare',

  // Entry log
  ENTRY_LOG_TITLE: 'Jurnal intrari',
  TIMESTAMP: 'Ora',
  PERSON_ID: 'ID Persoana',
  CONFIDENCE: 'Incredere',
  SNAPSHOT: 'Captura',

  // Keyboard shortcuts hint
  SHORTCUTS_HINT: 'F2: Start/Stop | F3: Overlay | F4: Test | Esc: Oprire urgenta',

  // Connection status
  WS_CONNECTING: 'Se conecteaza...',
  WS_CONNECTED: 'Conectat la server',
  WS_DISCONNECTED: 'Deconectat -- se reincearca...',

  // Feed
  FEED_LOADING: 'Se incarca feed-ul video...',
  FEED_ERROR: 'Eroare la incarcarea feed-ului',
  NO_FEED: 'Feed indisponibil',

  // Video overlay
  VIDEO_IDLE: 'Asteptare...',
  VIDEO_GREETING: 'Bine ati venit',
  VIDEO_ASK_NAME: 'Va rugam spuneti numele',
  VIDEO_ASK_QUESTION: 'Va rugam raspundeti',
  VIDEO_ASK_CNP: 'Va rugam spuneti CNP-ul',
  VIDEO_ASK_EMAIL: 'Va rugam spuneti adresa de email',
  VIDEO_FAREWELL: 'Va multumim',
  VIDEO_FINAL: 'La revedere',
  VIDEO_LISTENING: 'Ascultare...',
  VIDEO_PROCESSING: 'Procesare...',

  // Audio recording
  RECORDING: 'Inregistrare...',
  PROCESSING: 'Procesare...',
  CONFIRM_PROMPT: 'Este corect?',
  CONFIRM_ACCEPT: 'Confirma',
  CONFIRM_RETRY: 'Repeta',
  CNP_LABEL: 'CNP',
  EMAIL_LABEL: 'Email',
  MIC_DENIED: 'Acces microfon refuzat',
  MIC_UNAVAILABLE: 'Microfon indisponibil',
  TRANSCRIPTION_EMPTY: 'Nu am inteles. Repetati va rog.',

  // Workflow state machine
  WORKFLOW_LISTENING: 'Ascultare...',
  WORKFLOW_CONFIRM_ALL: 'Verificati datele dumneavoastra:',
  WORKFLOW_NAME_LABEL: 'Nume',
  WORKFLOW_QUESTION_LABEL: 'Raspuns',
  WORKFLOW_SUBMITTING: 'Se trimite...',
  WORKFLOW_SUBMITTED: 'Date trimise cu succes',
  WORKFLOW_TIMEOUT: 'Timp expirat. Revenire la asteptare.',
  WORKFLOW_CONFIRM_SEND: 'Trimite',
  WORKFLOW_CONFIRM_CANCEL: 'Anuleaza',

  // System control
  SYSTEM_START: 'Start',
  SYSTEM_STOP: 'Stop',
  SYSTEM_STARTING: 'Se porneste...',
  SYSTEM_STOPPING: 'Se opreste...',
  CRASH_ALERT: 'Detectorul s-a oprit neasteptat!',
  CRASH_RESTART: 'Repornire',
  CRASH_RESTARTING: 'Se reporneste...',
} as const;
