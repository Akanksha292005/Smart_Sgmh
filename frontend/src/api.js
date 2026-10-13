// Thin fetch wrapper: attaches the bearer token and throws readable errors.
export const getAuth = () => JSON.parse(localStorage.getItem("auth") || "null");
export const setAuth = (a) => (a ? localStorage.setItem("auth", JSON.stringify(a)) : localStorage.removeItem("auth"));
export async function api(path, body) {
  const a = getAuth(), tk = a?.token || sessionStorage.getItem("trackToken");
  const r = await fetch("/api/v1" + path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", ...(tk && { Authorization: "Bearer " + tk }) },
    body: body && JSON.stringify(body),
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(d.error || "Request failed"), { status: r.status });
  return d;
}
