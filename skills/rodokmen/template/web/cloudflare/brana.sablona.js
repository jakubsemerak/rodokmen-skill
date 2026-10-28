// Přihlašovací brána pro Cloudflare Pages (Pages Functions). Soubor functions/_middleware.js z této šablony
// vyrábí tools/export_web.py – ručně neupravovat. Odpověď na rodinnou otázku tu není, jen její otisk (SHA-256),
// který přihlašovací stránka uloží do cookie.
const HASH = '{{HASH}}';

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.pathname === '/prihlaseni.html' || url.pathname === '/prihlaseni') return context.next();
  const cookie = (context.request.headers.get('cookie') || '').match(/(?:^|;\s*)rodokmen=([0-9a-f]{64})(?:;|$)/);
  if (cookie && cookie[1] === HASH) {
    const res = await context.next();
    const out = new Response(res.body, res);
    out.headers.set('X-Robots-Tag', 'noindex, nofollow');
    return out;
  }
  // Pages podává /prihlaseni.html jako /prihlaseni (bez přípony); přihlašovací stránka se ukáže na původní adrese,
  // takže po přihlášení zůstane návštěvník tam, kam šel (žádné přesměrování podle parametru → nejde zneužít).
  const login = await context.env.ASSETS.fetch(new URL('/prihlaseni', url));
  return new Response(await login.text(), {
    status: 401,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
