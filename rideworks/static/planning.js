/* Revisit date-sensitive suggestions at rider-local midnight / tab return. */
(() => {
  'use strict';
  const zone = document.documentElement.dataset.displayTimezone || 'America/Los_Angeles';
  for (const form of document.querySelectorAll('.plan-correction')) {
    if (!form.elements.tz.value) form.elements.tz.value = zone;
  }
  const card = document.querySelector('[data-recommended-day]');
  if (!card) return;
  const localDay = () => {
    const parts = new Intl.DateTimeFormat('en-CA', {year:'numeric',month:'2-digit',day:'2-digit',timeZone:zone}).formatToParts(new Date());
    return ['year','month','day'].map(k => parts.find(p => p.type === k).value).join('-');
  };
  function check() {
    if (localDay() !== card.dataset.recommendedDay) window.location.reload();
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  window.addEventListener('focus', check);
  window.setInterval(check, 30000);
})();
