/**
 * Central API Client Wrapper
 * Guarantees same-origin session credentials, structured JSON error handling,
 * and seamless redirection on authentication timeouts (HTTP 401).
 */
import { showToast } from './utils.js';

export async function fetchApi(endpoint, options = {}) {
  const defaultOptions = {
    credentials: 'same-origin',
    headers: {}
  };

  const isFormData = options.body instanceof FormData;
  if (!isFormData && options.body && typeof options.body === 'object') {
    defaultOptions.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  const finalOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...(options.headers || {})
    }
  };

  try {
    const response = await fetch(endpoint, finalOptions);

    // 401 Unauthorized -> Force session login screen
    if (response.status === 401) {
      document.documentElement.classList.remove('logged-in-session');
      const loginScreen = document.getElementById('login-screen');
      if (loginScreen) {
        loginScreen.style.display = 'flex';
        loginScreen.style.opacity = '1';
      }
      showToast('warning', 'Session Expired', 'Please sign in to continue.');
      throw new Error('Authentication required');
    }

    // 403 Forbidden -> Privilege error
    if (response.status === 403) {
      showToast('error', 'Access Denied', 'You do not have permission for this operation.');
      throw new Error('Forbidden: Insufficient privileges');
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data.error || `Request failed with status ${response.status}`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (err) {
    if (err.message !== 'Authentication required' && err.message !== 'Forbidden: Insufficient privileges') {
      console.error(`[API Error: ${endpoint}]`, err);
    }
    throw err;
  }
}
