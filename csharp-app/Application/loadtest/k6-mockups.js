import http from "k6/http";
import { check, group, sleep } from "k6";

export const options = {
    stages: [
        { duration: "20s", target: 5 },   // плавный разгон
        { duration: "40s", target: 5 },   // полка
        { duration: "20s", target: 15 },  // усиление
        { duration: "40s", target: 15 },  // полка
        { duration: "10s", target: 0 },   // спад
    ],
    thresholds: {
        http_req_failed: ["rate<0.01"],     // < 1% ошибок
        http_req_duration: ["p(95)<800"],   // p95 < 800ms (локально норм ориентир)
    },
};

const BASE_URL = __ENV.BASE_URL;

export default function () {
    group("pages", () => {
        // поменяем список под твои реальные страницы
        const paths = ["/", "/Menu/Index"];

        for (const p of paths) {
            const res = http.get(`${BASE_URL}${p}`, { redirects: 0 });

            check(res, {
                "status is 200": (r) => r.status === 200,
                // если у тебя будут редиректы на логин — заменим на (200 || 302)
            });
        }
    });

    sleep(1);
}