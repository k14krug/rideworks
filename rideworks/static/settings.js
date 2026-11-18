'use strict';
for (const form of document.querySelectorAll('form[data-settings-action]')) {
  form.addEventListener('submit', () => {
    for (const button of document.querySelectorAll('form[data-settings-action] button')) button.disabled = true;
    const button = form.querySelector('button');
    button.textContent = (form.action.endsWith('/annual-goal') || form.action.endsWith('/segments/add')) ? 'Saving…' : form.action.endsWith('/rebuild') ? 'Rebuilding…' : form.action.endsWith('/sync') ? 'Syncing…' : form.action.endsWith('/connect') ? 'Connecting…' : 'Disconnecting…';
  });
}
