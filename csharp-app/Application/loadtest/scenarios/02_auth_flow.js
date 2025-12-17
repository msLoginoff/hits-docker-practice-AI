import http from 'k6/http';
import { check, group, sleep } from 'k6';

export const options = {
    thresholds: {
        http_req_failed: ['rate<0.02'],
        http_req_duration: ['p(95)<1200'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5146';
const EMAIL = __ENV.EMAIL || 'Java@DlyaLox.ov';
const PASSWORD = __ENV.PASSWORD || '.NetDlyaPacan0v';

function extractToken(html) {
    const m = html.match(/name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"/);
    return m ? m[1] : null;
}

function formEncode(obj) {
    return Object.keys(obj)
        .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(obj[k])}`)
        .join('&');
}

export default function () {
    group('auth flow', () => {
        const loginGet = http.get(`${BASE_URL}/Account/Login`);
        check(loginGet, { 'login page 200': (r) => r.status === 200 });

        const token = extractToken(loginGet.body);
        check(token, { 'antiforgery token extracted': (t) => t !== null });

        const payload = formEncode({
            Email: EMAIL,
            Password: PASSWORD,
            __RequestVerificationToken: token,
        });

        const loginPost = http.post(`${BASE_URL}/Account/Login`, payload, {
            redirects: 0,
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
        check(loginPost, { 'login redirect 302': (r) => r.status === 302 });

        const acc = http.get(`${BASE_URL}/Account/Index`);
        check(acc, { 'account page 200': (r) => r.status === 200 });

        const logout = http.get(`${BASE_URL}/Account/Logout`, { redirects: 0 });
        check(logout, { 'logout redirect 302': (r) => r.status === 302 });
    });

    sleep(1);
}