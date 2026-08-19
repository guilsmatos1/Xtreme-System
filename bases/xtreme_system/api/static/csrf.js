function csrfToken() {
  var match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}
document.addEventListener("submit", function (event) {
  var form = event.target;
  if (form.method.toLowerCase() === "get" || form.querySelector('[name="csrf_token"]')) return;
  var token = csrfToken();
  if (!token) return;
  var input = document.createElement("input");
  input.type = "hidden";
  input.name = "csrf_token";
  input.value = token;
  form.appendChild(input);
});
document.addEventListener("htmx:configRequest", function (event) {
  var token = csrfToken();
  if (token) event.detail.headers["X-CSRFToken"] = token;
});
