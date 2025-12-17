import http from 'k6/http';
import { check, group, sleep } from 'k6';

export const options = {
    thresholds: {
        http_req_failed: ['rate<0.02'],
        http_req_duration: ['p(95)<1200'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:5146';
const EMAIL = __ENV.EMAIL || 'Java@DlyaLox.ov';
const PASSWORD = __ENV.PASSWORD || '.NetDlyaPacan0v';

function extractToken(html) {
    const m = html.match(/name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"/);
    return m ? m[1] : null;
}

function formEncode(obj) {
    return Object.keys(obj).map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(obj[k])}`).join('&');
}

function login() {
    const get = http.get(`${BASE_URL}/Account/Login`);
    const token = extractToken(get.body);
    const payload = formEncode({ Email: EMAIL, Password: PASSWORD, __RequestVerificationToken: token });

    const post = http.post(`${BASE_URL}/Account/Login`, payload, {
        redirects: 0,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    check(post, { 'admin login 302': (r) => r.status === 302 });
}

export default function () {
    group('admin browse', () => {
        login();

        const idx = http.get(`${BASE_URL}/OrdersManagement/Index`);
        check(idx, { 'orders management index 200': (r) => r.status === 200 });

        // можно ещё сходить в Create в меню (админу доступно)
        const menuCreate = http.get(`${BASE_URL}/Menu/Create`);
        check(menuCreate, { 'menu/create 200': (r) => r.status === 200 });
    });

    sleep(1);
}