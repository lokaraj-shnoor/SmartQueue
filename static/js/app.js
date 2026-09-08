// Two small conveniences. Everything else is server-rendered on purpose.
document.addEventListener("click", (event) => {
  const dismiss = event.target.closest("[data-dismiss]");
  if (dismiss) {
    dismiss.closest(".flash")?.remove();
  }
});

// Confirm before anything that removes a record.
document.addEventListener("submit", (event) => {
  const form = event.target;
  const question = form.dataset.confirm;
  if (question && !window.confirm(question)) {
    event.preventDefault();
  }
});
