/**
 * Authentication & Session Management Module
 */
import { fetchApi } from './api.js';
import { showToast, escapeHtml } from './utils.js';

export function initAuth(onLoginSuccess) {
  const loginForm = document.getElementById('login-form');
  const loginUser = document.getElementById('login-user');
  const loginPass = document.getElementById('login-pass');
  const loginBtn = document.getElementById('login-btn');
  const loginSpinner = document.getElementById('login-spinner');
  const logoutBtn = document.getElementById('logout-btn');
  const eyeToggle = document.getElementById('eye-toggle');

  if (eyeToggle && loginPass) {
    eyeToggle.addEventListener('click', () => {
      loginPass.type = loginPass.type === 'password' ? 'text' : 'password';
    });
  }

  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = loginUser.value.trim();
      const password = loginPass.value;

      if (!username || !password) {
        showToast('warning', 'Missing Fields', 'Please enter username and password.');
        return;
      }

      if (loginSpinner) loginSpinner.style.display = 'inline-block';
      if (loginBtn) loginBtn.disabled = true;

      try {
        const res = await fetchApi('/login', {
          method: 'POST',
          body: { username, password }
        });

        if (res.success) {
          showToast('success', 'Authenticated', res.message || 'Login successful!');
          document.documentElement.classList.add('logged-in-session');
          const loginScreen = document.getElementById('login-screen');
          if (loginScreen) {
            loginScreen.style.opacity = '0';
            setTimeout(() => { loginScreen.style.display = 'none'; }, 300);
          }
          updateProfileUI(res.user);
          if (onLoginSuccess) onLoginSuccess(res.user);
        }
      } catch (err) {
        showToast('error', 'Login Failed', err.message || 'Invalid credentials.');
      } finally {
        if (loginSpinner) loginSpinner.style.display = 'none';
        if (loginBtn) loginBtn.disabled = false;
      }
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        await fetchApi('/logout', { method: 'POST' });
      } catch (e) {}
      document.documentElement.classList.remove('logged-in-session');
      const loginScreen = document.getElementById('login-screen');
      if (loginScreen) {
        loginScreen.style.display = 'flex';
        loginScreen.style.opacity = '1';
      }
      showToast('info', 'Logged Out', 'You have been safely signed out.');
    });
  }
}

export function updateProfileUI(user) {
  if (!user) return;
  // Update topbar & dropdowns
  const topWho = document.querySelector('.topbar-profile .who');
  const topRole = document.querySelector('.topbar-profile .role');
  const avatar = document.querySelector('.topbar-profile .avatar');
  const pdName = document.querySelector('.pd-name');
  const pdRole = document.querySelector('.pd-role');
  const pdValues = document.querySelectorAll('.pd-value');

  const initials = user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'AD';

  if (topWho) topWho.textContent = user.name;
  if (topRole) topRole.textContent = `${user.role.toUpperCase()} · ${user.department || 'Traffic Control'}`;
  if (avatar) avatar.textContent = initials;
  if (pdName) pdName.textContent = user.name;
  if (pdRole) pdRole.textContent = `${user.role.toUpperCase()} · Control Unit`;

  if (pdValues && pdValues.length >= 4) {
    pdValues[0].textContent = `KCH-2026-${user.id.toString().padStart(4, '0')}`;
    pdValues[1].textContent = user.department || 'Kochi City Traffic Safety Unit';
    pdValues[2].textContent = user.email;
    pdValues[3].textContent = user.role.toUpperCase();
  }
}

export async function checkSession() {
  try {
    const res = await fetchApi('/api/profile');
    if (res.success && res.user) {
      document.documentElement.classList.add('logged-in-session');
      const loginScreen = document.getElementById('login-screen');
      if (loginScreen) loginScreen.style.display = 'none';
      updateProfileUI(res.user);
      return res.user;
    }
  } catch (err) {
    // Session not active
  }
  return null;
}
