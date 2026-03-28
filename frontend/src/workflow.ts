/**
 * Patient workflow state machine — Form version.
 *
 * Two independent flows:
 *
 * 1. DETECTION: person enters → mp3 + form → submit → thank_you → idle
 * 2. CALL PATIENT: receptionist button → CHEAMAPACIENT.mp4 video → idle
 *
 * States: stopped → idle → form → form_submitting → thank_you → idle
 *                        → greeting (call patient video) → idle
 */

import { apiSubmitPatient } from './api.ts';
import type { EventLogEntry, WorkflowState } from './types.ts';
import { hideTranscriptionPanel } from './ui.ts';
import { hideVideo, hideMarquee, playSingleVideo } from './video.ts';

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------

const THANK_YOU_DURATION = 6_000;
const FORM_TIMEOUT = 120_000;

// ---------------------------------------------------------------------------
//  Translations
// ---------------------------------------------------------------------------

interface FormStrings {
  title: string;
  subtitle: string;
  nume: string;
  prenume: string;
  email: string;
  cnp: string;
  numePlaceholder: string;
  prenumePlaceholder: string;
  emailPlaceholder: string;
  cnpPlaceholder: string;
  submit: string;
  thankYouTitle: string;
  thankYouMsg: string;
}

const TRANSLATIONS: Record<string, FormStrings> = {
  ro: { title: 'Bine ati venit!', subtitle: 'Completati datele pentru inregistrare', nume: 'Nume', prenume: 'Prenume', email: 'Adresa de email', cnp: 'CNP', numePlaceholder: 'Popescu', prenumePlaceholder: 'Ion', emailPlaceholder: 'exemplu@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Confirma si trimite', thankYouTitle: 'Multumesc!', thankYouMsg: 'Va rugam sa luati un loc\npana sunteti chemat.' },
  en: { title: 'Welcome!', subtitle: 'Please fill in your details', nume: 'Last name', prenume: 'First name', email: 'Email address', cnp: 'CNP (Personal ID)', numePlaceholder: 'Smith', prenumePlaceholder: 'John', emailPlaceholder: 'example@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Confirm and submit', thankYouTitle: 'Thank you!', thankYouMsg: 'Please take a seat\nuntil you are called.' },
  uk: { title: 'Ласкаво просимо!', subtitle: 'Будь ласка, заповніть ваші дані', nume: 'Прізвище', prenume: "Ім'я", email: 'Електронна пошта', cnp: 'CNP (Особистий код)', numePlaceholder: 'Шевченко', prenumePlaceholder: 'Олена', emailPlaceholder: 'приклад@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Підтвердити та надіслати', thankYouTitle: 'Дякуємо!', thankYouMsg: 'Будь ласка, сідайте\nта чекайте виклику.' },
  hu: { title: 'Üdvözöljük!', subtitle: 'Kérjük, töltse ki az adatait', nume: 'Vezetéknév', prenume: 'Keresztnév', email: 'Email cím', cnp: 'CNP (Személyi szám)', numePlaceholder: 'Nagy', prenumePlaceholder: 'János', emailPlaceholder: 'pelda@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Megerősítés és küldés', thankYouTitle: 'Köszönjük!', thankYouMsg: 'Kérjük, foglaljon helyet\namíg szólítjuk.' },
  de: { title: 'Willkommen!', subtitle: 'Bitte füllen Sie Ihre Daten aus', nume: 'Nachname', prenume: 'Vorname', email: 'E-Mail-Adresse', cnp: 'CNP (Persönliche ID)', numePlaceholder: 'Müller', prenumePlaceholder: 'Hans', emailPlaceholder: 'beispiel@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Bestätigen und senden', thankYouTitle: 'Danke!', thankYouMsg: 'Bitte nehmen Sie Platz\nbis Sie aufgerufen werden.' },
  fr: { title: 'Bienvenue!', subtitle: 'Veuillez remplir vos données', nume: 'Nom', prenume: 'Prénom', email: 'Adresse e-mail', cnp: 'CNP (ID personnel)', numePlaceholder: 'Dupont', prenumePlaceholder: 'Marie', emailPlaceholder: 'exemple@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Confirmer et envoyer', thankYouTitle: 'Merci!', thankYouMsg: 'Veuillez prendre place\njusqu\'à ce qu\'on vous appelle.' },
  it: { title: 'Benvenuto!', subtitle: 'Compilate i vostri dati', nume: 'Cognome', prenume: 'Nome', email: 'Indirizzo email', cnp: 'CNP (ID personale)', numePlaceholder: 'Rossi', prenumePlaceholder: 'Marco', emailPlaceholder: 'esempio@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Conferma e invia', thankYouTitle: 'Grazie!', thankYouMsg: 'Prendete posto\nfino alla chiamata.' },
  es: { title: '¡Bienvenido!', subtitle: 'Por favor complete sus datos', nume: 'Apellido', prenume: 'Nombre', email: 'Correo electrónico', cnp: 'CNP (ID personal)', numePlaceholder: 'García', prenumePlaceholder: 'Carlos', emailPlaceholder: 'ejemplo@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Confirmar y enviar', thankYouTitle: '¡Gracias!', thankYouMsg: 'Por favor tome asiento\nhasta que le llamen.' },
  ru: { title: 'Добро пожаловать!', subtitle: 'Пожалуйста, заполните ваши данные', nume: 'Фамилия', prenume: 'Имя', email: 'Электронная почта', cnp: 'CNP (Личный код)', numePlaceholder: 'Иванов', prenumePlaceholder: 'Иван', emailPlaceholder: 'пример@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Подтвердить и отправить', thankYouTitle: 'Спасибо!', thankYouMsg: 'Пожалуйста, присаживайтесь\nи ждите вызова.' },
  tr: { title: 'Hoş geldiniz!', subtitle: 'Lütfen bilgilerinizi doldurun', nume: 'Soyadı', prenume: 'Adı', email: 'E-posta adresi', cnp: 'CNP (Kişisel kimlik)', numePlaceholder: 'Yılmaz', prenumePlaceholder: 'Ahmet', emailPlaceholder: 'ornek@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Onayla ve gönder', thankYouTitle: 'Teşekkürler!', thankYouMsg: 'Lütfen yerinize oturun\nçağrılana kadar bekleyin.' },
  bg: { title: 'Добре дошли!', subtitle: 'Моля, попълнете данните си', nume: 'Фамилия', prenume: 'Име', email: 'Имейл адрес', cnp: 'CNP (Личен код)', numePlaceholder: 'Иванов', prenumePlaceholder: 'Георги', emailPlaceholder: 'пример@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Потвърди и изпрати', thankYouTitle: 'Благодаря!', thankYouMsg: 'Моля, заемете място\nдокато ви повикат.' },
  ar: { title: '!مرحبا', subtitle: 'يرجى ملء بياناتكم', nume: 'اسم العائلة', prenume: 'الاسم الأول', email: 'البريد الإلكتروني', cnp: 'CNP (الرقم الشخصي)', numePlaceholder: 'محمد', prenumePlaceholder: 'أحمد', emailPlaceholder: 'مثال@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'تأكيد وإرسال', thankYouTitle: '!شكرا', thankYouMsg: 'يرجى الجلوس\nحتى يتم استدعاؤكم.' },
  pt: { title: 'Bem-vindo!', subtitle: 'Por favor preencha os seus dados', nume: 'Apelido', prenume: 'Nome', email: 'Endereço de email', cnp: 'CNP (ID pessoal)', numePlaceholder: 'Silva', prenumePlaceholder: 'João', emailPlaceholder: 'exemplo@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Confirmar e enviar', thankYouTitle: 'Obrigado!', thankYouMsg: 'Por favor tome assento\naté ser chamado.' },
  zh: { title: '欢迎！', subtitle: '请填写您的信息', nume: '姓', prenume: '名', email: '电子邮件', cnp: 'CNP（个人身份号）', numePlaceholder: '王', prenumePlaceholder: '明', emailPlaceholder: 'example@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: '确认并提交', thankYouTitle: '谢谢！', thankYouMsg: '请就座\n等待叫号。' },
  hi: { title: 'स्वागत है!', subtitle: 'कृपया अपना विवरण भरें', nume: 'उपनाम', prenume: 'नाम', email: 'ईमेल पता', cnp: 'CNP (व्यक्तिगत आईडी)', numePlaceholder: 'शर्मा', prenumePlaceholder: 'राज', emailPlaceholder: 'example@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'पुष्टि करें और भेजें', thankYouTitle: 'धन्यवाद!', thankYouMsg: 'कृपया बैठ जाइए\nजब तक आपको बुलाया न जाए।' },
  bn: { title: 'স্বাগতম!', subtitle: 'অনুগ্রহ করে আপনার তথ্য পূরণ করুন', nume: 'পদবি', prenume: 'নাম', email: 'ইমেইল ঠিকানা', cnp: 'CNP (ব্যক্তিগত আইডি)', numePlaceholder: 'রহমান', prenumePlaceholder: 'করিম', emailPlaceholder: 'example@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'নিশ্চিত করুন ও পাঠান', thankYouTitle: 'ধন্যবাদ!', thankYouMsg: 'অনুগ্রহ করে বসুন\nডাকা পর্যন্ত অপেক্ষা করুন।' },
  pl: { title: 'Witamy!', subtitle: 'Proszę wypełnić swoje dane', nume: 'Nazwisko', prenume: 'Imię', email: 'Adres e-mail', cnp: 'CNP (Numer osobisty)', numePlaceholder: 'Kowalski', prenumePlaceholder: 'Jan', emailPlaceholder: 'przyklad@email.com', cnpPlaceholder: '_ _ _ _ _ _ _ _ _ _ _ _ _', submit: 'Potwierdź i wyślij', thankYouTitle: 'Dziękujemy!', thankYouMsg: 'Proszę usiąść\ni czekać na wezwanie.' },
};

function getStrings(): FormStrings {
  const sel = document.getElementById('lang-select') as HTMLSelectElement | null;
  const lang = sel?.value || 'ro';
  return TRANSLATIONS[lang] || TRANSLATIONS['ro'];
}

function applyLanguage(): void {
  const s = getStrings();
  const title = document.getElementById('form-title');
  const subtitle = document.getElementById('form-subtitle');
  const lblNume = document.querySelector('label[for="form-nume"]');
  const lblPrenume = document.querySelector('label[for="form-prenume"]');
  const lblEmail = document.querySelector('label[for="form-email"]');
  const lblCnp = document.querySelector('label[for="form-cnp"]');
  const inpNume = document.getElementById('form-nume') as HTMLInputElement | null;
  const inpPrenume = document.getElementById('form-prenume') as HTMLInputElement | null;
  const inpEmail = document.getElementById('form-email') as HTMLInputElement | null;
  const inpCnp = document.getElementById('form-cnp') as HTMLInputElement | null;
  const btnText = document.querySelector('.form-submit-btn .btn-text');
  const tyTitle = document.querySelector('.thank-you-card h2');
  const tyMsg = document.querySelector('.thank-you-card p');

  if (title) title.textContent = s.title;
  if (subtitle) subtitle.textContent = s.subtitle;
  if (lblNume) lblNume.textContent = s.nume;
  if (lblPrenume) lblPrenume.textContent = s.prenume;
  if (lblEmail) lblEmail.textContent = s.email;
  if (lblCnp) lblCnp.textContent = s.cnp;
  if (inpNume) inpNume.placeholder = s.numePlaceholder;
  if (inpPrenume) inpPrenume.placeholder = s.prenumePlaceholder;
  if (inpEmail) inpEmail.placeholder = s.emailPlaceholder;
  if (inpCnp) inpCnp.placeholder = s.cnpPlaceholder;
  if (btnText) btnText.textContent = s.submit;
  if (tyTitle) tyTitle.textContent = s.thankYouTitle;
  if (tyMsg) tyMsg.innerHTML = s.thankYouMsg.replace('\n', '<br/>');
}

// ---------------------------------------------------------------------------
//  Module-level state
// ---------------------------------------------------------------------------

let currentState: WorkflowState = 'stopped';
let stateTimeout: ReturnType<typeof setTimeout> | null = null;
let callPatientQueue = 0;

// ---------------------------------------------------------------------------
//  DOM refs
// ---------------------------------------------------------------------------

function formOverlay(): HTMLElement | null {
  return document.getElementById('patient-form-overlay');
}

function thankYouOverlay(): HTMLElement | null {
  return document.getElementById('thank-you-overlay');
}

function patientForm(): HTMLFormElement | null {
  return document.getElementById('patient-form') as HTMLFormElement | null;
}

function greetingAudio(): HTMLAudioElement | null {
  return document.getElementById('greeting-audio') as HTMLAudioElement | null;
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

function clearStateTimeout(): void {
  if (stateTimeout !== null) {
    clearTimeout(stateTimeout);
    stateTimeout = null;
  }
}

function hideForm(): void {
  const overlay = formOverlay();
  if (overlay) overlay.classList.remove('visible');
}

function hideThankYou(): void {
  const overlay = thankYouOverlay();
  if (overlay) overlay.classList.remove('visible');
}

function resetForm(): void {
  const form = patientForm();
  if (form) form.reset();
}

function playGreeting(): void {
  const audio = greetingAudio();
  if (audio) {
    audio.currentTime = 0;
    audio.play().catch(() => {});
  }
}

function stopGreeting(): void {
  const audio = greetingAudio();
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
  }
}

function hideAll(): void {
  hideForm();
  hideThankYou();
  hideTranscriptionPanel();
  hideMarquee();
  hideVideo();
}

// ---------------------------------------------------------------------------
//  State machine
// ---------------------------------------------------------------------------

function transition(newState: WorkflowState): void {
  clearStateTimeout();
  const prevState = currentState;
  currentState = newState;
  console.log(`workflow: ${prevState} -> ${newState}`);
  executeStateEntry(newState);
}

function executeStateEntry(state: WorkflowState): void {
  switch (state) {
    case 'stopped':
      hideAll();
      break;

    case 'idle':
      hideAll();
      notifyKioskState('idle');
      // Drain call-patient queue
      if (callPatientQueue > 0) {
        callPatientQueue--;
        setTimeout(() => {
          if (currentState === 'idle') transition('greeting');
        }, 1500);
      }
      break;

    case 'form':
      executeForm();
      break;

    case 'form_submitting':
      executeFormSubmit();
      break;

    case 'thank_you':
      executeThankYou();
      break;

    case 'greeting':
      executeCallPatientVideo();
      break;

    default:
      break;
  }
}

// ---------------------------------------------------------------------------
//  FLOW 1: Detection → Form
// ---------------------------------------------------------------------------

function notifyKioskState(kioskState: string): void {
  fetch('/api/kiosk-state', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state: kioskState }),
  }).catch(() => {});
}

function executeForm(): void {
  hideAll();

  const overlay = formOverlay();
  if (overlay) overlay.classList.add('visible');

  resetForm();
  applyLanguage();
  playGreeting();
  notifyKioskState('form');

  const numeInput = document.getElementById('form-nume') as HTMLInputElement | null;
  if (numeInput) setTimeout(() => numeInput.focus(), 100);

  stateTimeout = setTimeout(() => {
    if (currentState === 'form') {
      console.warn('workflow: form timeout, returning to idle');
      stopGreeting();
      fetch('/api/form-abandoned', { method: 'POST' }).catch(() => {});
      transition('idle');
    }
  }, FORM_TIMEOUT);
}

function onFormSubmit(e: Event): void {
  e.preventDefault();
  if (currentState !== 'form') return;
  transition('form_submitting');
}

function executeFormSubmit(): void {
  const numeEl = document.getElementById('form-nume') as HTMLInputElement | null;
  const prenumeEl = document.getElementById('form-prenume') as HTMLInputElement | null;
  const emailEl = document.getElementById('form-email') as HTMLInputElement | null;
  const cnpEl = document.getElementById('form-cnp') as HTMLInputElement | null;
  const submitBtn = patientForm()?.querySelector('button[type="submit"]') as HTMLButtonElement | null;

  const nume = numeEl?.value.trim() || '';
  const prenume = prenumeEl?.value.trim() || '';
  const email = emailEl?.value.trim() || '';
  const cnp = cnpEl?.value.trim() || '';

  if (submitBtn) submitBtn.disabled = true;
  stopGreeting();

  const patientData = {
    name: `${prenume} ${nume}`.trim(),
    question: null,
    cnp: cnp || null,
    phone: null,
    email: email || null,
  };

  apiSubmitPatient(patientData)
    .then((response) => {
      if (currentState !== 'form_submitting') return;

      if (response.sign_url) {
        fetch('/api/sign-ready', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sign_url: response.sign_url }),
        }).catch(() => {});
      }

      transition('thank_you');
    })
    .catch((err: unknown) => {
      console.error('workflow: submit failed', err);
      if (currentState !== 'form_submitting') return;
      transition('thank_you');
    })
    .finally(() => {
      if (submitBtn) submitBtn.disabled = false;
    });
}

function executeThankYou(): void {
  hideForm();
  notifyKioskState('thank_you');

  const overlay = thankYouOverlay();
  if (overlay) overlay.classList.add('visible');

  stateTimeout = setTimeout(() => {
    if (currentState === 'thank_you') {
      transition('idle');
    }
  }, THANK_YOU_DURATION);
}

// ---------------------------------------------------------------------------
//  FLOW 2: Call Patient → Video CHEAMAPACIENT.mp4
// ---------------------------------------------------------------------------

function executeCallPatientVideo(): void {
  hideAll();
  notifyKioskState('calling');

  playSingleVideo('CHEAMAPACIENT.mp4', () => {
    fetch('/api/call-patient-done', { method: 'POST' }).catch(() => {});
    transition('idle');
  });
}

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------

export function initWorkflow(): void {
  currentState = 'stopped';

  const form = patientForm();
  if (form) {
    form.addEventListener('submit', onFormSubmit);
  }

  // Wire language selector
  const langSel = document.getElementById('lang-select');
  if (langSel) {
    langSel.addEventListener('change', applyLanguage);
  }
  applyLanguage();
}

export function startWorkflow(): void {
  if (currentState !== 'stopped') return;
  transition('idle');
}

export function stopWorkflow(): void {
  clearStateTimeout();
  stopGreeting();
  hideAll();
  resetForm();
  currentState = 'stopped';
  console.log('workflow: stopped');
}

export function getWorkflowState(): WorkflowState {
  return currentState;
}

export function getPatientData(): Readonly<{ name: string | null; question: string | null; cnp: string | null; phone: string | null; email: string | null }> {
  return { name: null, question: null, cnp: null, phone: null, email: null };
}

export function onPersonEntered(): void {
  if (currentState === 'idle') {
    transition('form');
  }
}

// ---------------------------------------------------------------------------
//  Call-patient (receptionist button → play CHEAMAPACIENT.mp4)
// ---------------------------------------------------------------------------

let lastCallPatientTimestamp: string | null = null;

export function checkForCallPatient(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'call_patient');
  if (!latest) return;
  if (latest.timestamp === lastCallPatientTimestamp) return;

  lastCallPatientTimestamp = latest.timestamp;

  if (currentState === 'idle' || currentState === 'stopped') {
    if (currentState === 'stopped') currentState = 'idle';
    transition('greeting');
  } else {
    // Busy (form/thank_you) — queue, will play after returning to idle
    callPatientQueue++;
    console.log(`workflow: call_patient queued (queue=${callPatientQueue})`);
  }
}

// ---------------------------------------------------------------------------
//  Person-entered detection → show form
// ---------------------------------------------------------------------------

let lastPersonEnteredTimestamp: string | null = null;

export function checkForPersonEnteredWorkflow(eventLog: EventLogEntry[]): void {
  const latest = eventLog.find((e) => e.event === 'person_entered' || e.event === 'signin_started');
  if (!latest) return;
  if (latest.timestamp === lastPersonEnteredTimestamp) return;

  lastPersonEnteredTimestamp = latest.timestamp;

  if (currentState === 'idle') {
    transition('form');
  } else if (currentState === 'stopped') {
    currentState = 'idle';
    transition('form');
  }
}
