import http from "k6/http";
import { check, group, sleep } from "k6";

export const options = {
    insecureSkipTLSVerify: true,

    stages: [
        { duration: "15s", target: 3 },
        { duration: "30s", target: 3 },
        { duration: "15s", target: 8 },
        { duration: "30s", target: 8 },
        { duration: "10s", target: 0 },
    ],

    thresholds: {
        http_req_failed: ["rate<0.02"],
        http_req_duration: ["p(95)<1200"],
    },
};

const BASE_URL = __ENV.BASE_URL || "https://host.docker.internal:7146";
const EMAIL = __ENV.EMAIL || "Java@DlyaLox.ov";
const PASSWORD = __ENV.PASSWORD || ".NetDlyaPacan0v";

function extractAntiForgeryToken(html) {
    const m = html.match(/name="__RequestVerificationToken" type="hidden" value="([^"]+)"/);
    return m ? m[1] : null;
}

function formEncode(obj) {
    return Object.keys(obj)
        .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(obj[k])}`)
        .join("&");
}

export default function () {
    group("auth flow", () => {
        // 1) GET login page (получить токен + cookie)
        const loginPage = http.get(`${BASE_URL}/Account/Login`, { redirects: 0 });

        check(loginPage, {
            "login page 200": (r) => r.status === 200,
        });

        const token = extractAntiForgeryToken(loginPage.body);
        check(token, { "antiforgery token extracted": (t) => t !== null });

        // 2) POST login
        const body = formEncode({
            Email: EMAIL,
            Password: PASSWORD,
            __RequestVerificationToken: token,
        });

        const loginRes = http.post(`${BASE_URL}/Account/Login`, body, {
            redirects: 0,
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
        });

        // успешный логин обычно 302
        check(loginRes, {
            "login redirect 302": (r) => r.status === 302,
        });

        // 3) защищенная страница (проверка, что куки реально работают)
        const account = http.get(`${BASE_URL}/Account/Index`, { redirects: 0 });
        check(account, {
            "account page 200": (r) => r.status === 200,
        });

        // 4) logout
        const logout = http.get(`${BASE_URL}/Account/Logout`, { redirects: 0 });
        check(logout, {
            "logout redirect 302": (r) => r.status === 302,
        });
    });

    // важный момент: делаем поведение похожим на человека
    sleep(1);
}