/**
 * api.js - Centralized, defensive API client wrapper
 * - Validates HTTP status and Content-Type before parsing JSON
 * - Throws structured ApiError (no empty catch or silent failures)
 * - Intercepts 401 Unauthorized -> redirects to login
 * - Supports XMLHttpRequest uploads with upload progress & abort capability
 */

class ApiError extends Error {
  constructor(status, message, code = null, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || status;
    this.details = details;
  }
}

async function apiFetch(endpoint, options = {}) {
  const defaultHeaders = {
    'Accept': 'application/json'
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {})
    }
  };

  let response;
  try {
    response = await fetch(endpoint, config);
  } catch (netErr) {
    console.error(`[API Network Error] ${endpoint}:`, netErr);
    throw new ApiError(0, `Network error: Unable to connect to server. Check your connection.`);
  }

  // Handle 401 Unauthorized
  if (response.status === 401) {
    console.warn(`[API 401] Session expired or unauthenticated at ${endpoint}`);
    const loginScreen = document.getElementById('login-screen');
    if (loginScreen) {
      loginScreen.style.display = 'flex';
      loginScreen.classList.remove('hidden');
    }
    throw new ApiError(401, 'Authentication required. Please log in.');
  }

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json') || contentType.includes('application/problem+json');

  if (!isJson) {
    const rawText = await response.text().catch(() => '');
    console.error(`[API Non-JSON Response] HTTP ${response.status} from ${endpoint}. Content-Type: ${contentType}`, rawText.slice(0, 300));
    throw new ApiError(
      response.status,
      `Server returned an unexpected response (HTTP ${response.status}). See server log.`
    );
  }

  let data;
  try {
    data = await response.json();
  } catch (jsonErr) {
    console.error(`[API JSON Parse Error] ${endpoint}:`, jsonErr);
    throw new ApiError(response.status, `Failed to parse response as JSON (HTTP ${response.status}).`);
  }

  if (!response.ok || (data && data.success === false)) {
    const errorMsg = (data && data.error) ? data.error : `Request failed with status ${response.status}`;
    console.error(`[API Error] ${endpoint} (HTTP ${response.status}):`, errorMsg);
    throw new ApiError(response.status, errorMsg, data?.code);
  }

  return data;
}

/**
 * Perform multipart/form-data upload using XMLHttpRequest for reliable progress tracking
 */
function apiUpload(endpoint, formData, onProgress = null) {
  let xhrRef = null;

  const promise = new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhrRef = xhr;
    xhr.open('POST', endpoint, true);
    xhr.setRequestHeader('Accept', 'application/json');

    if (onProgress && xhr.upload) {
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          const percent = Math.round((evt.loaded / evt.total) * 100);
          onProgress({
            loaded: evt.loaded,
            total: evt.total,
            percent: Math.min(percent, 100)
          });
        }
      };
    }

    xhr.onload = () => {
      const status = xhr.status;
      if (status === 401) {
        const loginScreen = document.getElementById('login-screen');
        if (loginScreen) {
          loginScreen.style.display = 'flex';
          loginScreen.classList.remove('hidden');
        }
        return reject(new ApiError(401, 'Authentication required. Please log in.'));
      }

      const contentType = xhr.getResponseHeader('content-type') || '';
      const isJson = contentType.includes('application/json');

      if (!isJson) {
        console.error(`[Upload Non-JSON] HTTP ${status}. Response sample:`, (xhr.responseText || '').slice(0, 300));
        let safeMsg = `Server returned an unexpected response (HTTP ${status}). See server log.`;
        if (status === 413) {
          safeMsg = 'File too large. Maximum allowed size exceeded.';
        }
        return reject(new ApiError(status, safeMsg));
      }

      let parsed;
      try {
        parsed = JSON.parse(xhr.responseText);
      } catch (e) {
        return reject(new ApiError(status, `Failed to parse upload response (HTTP ${status}).`));
      }

      if (status >= 200 && status < 300 && parsed.success !== false) {
        resolve(parsed);
      } else {
        const msg = parsed.error || `Upload failed with status ${status}`;
        reject(new ApiError(status, msg, parsed.code));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError(0, 'Network error occurred during file upload. Check server connectivity.'));
    };

    xhr.onabort = () => {
      reject(new ApiError(0, 'Upload was cancelled by user.'));
    };

    xhr.send(formData);
  });

  promise.abort = () => {
    if (xhrRef) xhrRef.abort();
  };

  return promise;
}

window.ApiError = ApiError;
window.apiFetch = apiFetch;
window.apiUpload = apiUpload;
