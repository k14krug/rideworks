(() => {
  const form = document.querySelector('.race-review-form');
  if (!form) return;
  const confirm = form.querySelector('button[value="confirm"]');
  const notice = form.querySelector('.race-review-dirty');
  let dirty = false;
  const update = () => {
    const approvals = [...form.querySelectorAll('.race-approval')];
    confirm.disabled = dirty || form.dataset.matched !== 'true' || approvals.some(input => !input.checked);
    notice.hidden = !dirty;
  };
  form.addEventListener('input', event => {
    if (!event.target.classList.contains('race-approval')) {
      dirty = true;
      form.querySelector('input[name="list_acknowledged"]').checked = false;
      form.querySelectorAll('.race-conflict-verification').forEach(input => { input.checked = false; });
    }
    update();
  });
  update();
})();
