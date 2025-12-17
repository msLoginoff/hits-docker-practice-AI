import http from "k6/http";
import { check, group, sleep } from "k6";

export const options = {
    insecureSkipTLSVerify: true,

    stages: [
        { duration: "15s", target: 5 },
        { duration: "30s", target: 5 },
        { duration: "15s", target: 15 },
        { duration: "30s", target: 15 },
        { duration: "10s", target: 0 },
    ],

    thresholds: {
        http_req_failed: ["rate<0.01"],       // < 1% ошибок
        http_req_duration: ["p(95)<800"],     // p95 < 800ms (для локалки адекватно)
    },
};

const BASE_URL = __ENV.BASE_URL || "https://localhost:7146";

export default function () {
    group("menu pages (anonymous)", () => {
        // Главная = Menu/Index по твоему routing’у
        const urls = [
            "/",
            "/Menu/Index?filterIsVegan=true",
            "/Menu/Index?filterCategory=Pizza&filterCategory=Soup",
            "/Menu/Index?filterCategory=Dessert",
        ];

        for (const u of urls) {
            const res = http.get(`${BASE_URL}${u}`, { redirects: 0 });

            check(res, {
                "status 200": (r) => r.status === 200,
            });
        }
    });

    sleep(1);
}