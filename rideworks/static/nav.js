'use strict';

// Keep a user's open menu open when following a link to another page.
const powerNavigation = document.getElementById('power-nav');
try {
  powerNavigation.open = sessionStorage.getItem('rideworks.powerNavigationOpen') === 'true';
  powerNavigation.addEventListener('toggle', () => {
    try { sessionStorage.setItem('rideworks.powerNavigationOpen', String(powerNavigation.open)); }
    catch (_) { /* The native disclosure remains usable without storage. */ }
  });
} catch (_) { /* Storage may be unavailable; the disclosure still works. */ }
