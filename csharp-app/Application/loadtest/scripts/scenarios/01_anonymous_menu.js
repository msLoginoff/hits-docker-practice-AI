import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    thresholds: {
        http_req_failed: ['rate<0.01'],
        http_req_duration: ['p(95)<800'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:5146 ';

export default function () {
    const res = http.get(`${BASE_URL}/Menu/Index`, { redirects: 0 });
    check(res, { 'menu page 200': (r) => r.status === 200 });

    // лёгкая имитация "юзер читает страницу"
    sleep(1);
}