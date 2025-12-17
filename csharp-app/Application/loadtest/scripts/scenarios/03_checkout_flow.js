import http from 'k6/http';
import { check, group, sleep } from 'k6';

export const options = {
    thresholds: {
        http_req_failed: ['rate<0.02'],
        http_req_duration: ['p(95)<1500'],
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://host.docker.internal:5146';
const USER_COUNT = parseInt(__ENV.USER_COUNT || '10', 10);

function extractToken(html) {
    const m = html.match(/name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"/);
    return m ? m[1] : null;
}

function formEncode(obj) {
    return Object.keys(obj)
        .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(obj[k])}`)
        .join('&');
}

function registerUser(email, password) {
    const regGet = http.get(`${BASE_URL}/Account/Register`);
    const token = extractToken(regGet.body);
    check(token, { 'register token extracted': (t) => t !== null });

    const payload = formEncode({
        Name: 'Load Test User',
        Phone: '79990000000',
        BirthDate: '1995-01-01',
        Email: email,
        Password: password,
        __RequestVerificationToken: token,
    });

    const regPost = http.post(`${BASE_URL}/Account/Register`, payload, {
        redirects: 0,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    // может быть 302 на меню, или 200 с ошибкой валидации — считаем ок только успешный редирект
    check(regPost, { 'register redirect 302': (r) => r.status === 302 });
}

function login(email, password) {
    const loginGet = http.get(`${BASE_URL}/Account/Login`);
    const token = extractToken(loginGet.body);
    check(token, { 'login token extracted': (t) => t !== null });

    const payload = formEncode({
        Email: email,
        Password: password,
        __RequestVerificationToken: token,
    });

    const loginPost = http.post(`${BASE_URL}/Account/Login`, payload, {
        redirects: 0,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    check(loginPost, { 'login ok (302)': (r) => r.status === 302 });
}

function ensureAddress() {
    const addrGet = http.get(`${BASE_URL}/Account/AddAddress`);
    const token = extractToken(addrGet.body);
    check(token, { 'add address token extracted': (t) => t !== null });

    const payload = formEncode({
        Name: 'Home',
        StreetName: 'Street',
        HouseNumber: '1',
        EntranceNumber: '1',
        FlatNumber: '1',
        IsMainAddress: 'true',
        Note: 'loadtest',
        __RequestVerificationToken: token,
    });

    const addrPost = http.post(`${BASE_URL}/Account/AddAddress`, payload, {
        redirects: 0,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    check(addrPost, { 'address saved (302)': (r) => r.status === 302 });
}

function htmlDecode(s) {
    return s.replace(/&amp;/g, '&');
}

function pickFirstAddToCartUrl(menuHtml) {
    // ищем href содержащий /Menu/AddToCart
    const m = menuHtml.match(/href="([^"]*\/Menu\/AddToCart[^"]*)"/i);
    return m ? htmlDecode(m[1]) : null;
}

function addToCart(addToCartUrl) {
    if (!addToCartUrl) return null;
    const url = addToCartUrl.startsWith('http') ? addToCartUrl : `${BASE_URL}${addToCartUrl}`;

    const get = http.get(url);
    check(get, { 'add-to-cart page 200': (r) => r.status === 200 });

    const token = extractToken(get.body);
    check(token, { 'add-to-cart token extracted': (t) => t !== null });

    const payload = formEncode({
        Amount: '1',
        __RequestVerificationToken: token,
    });

    const post = http.post(url, payload, {
        redirects: 0,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    check(post, { 'add-to-cart redirect 302': (r) => r.status === 302 });
    return post;
}

function firstOptionValueBySelectId(html, selectId) {
    const re = new RegExp(`id="${selectId}"[\\s\\S]*?<option\\s+value="([^"]+)"`, 'i');
    const m = html.match(re);
    return m ? htmlDecode(m[1]) : null;
}

function createOrder() {
    const createGet = http.get(`${BASE_URL}/Orders/Create`);
    check(createGet, { 'orders/create 200': (r) => r.status === 200 });

    const token = extractToken(createGet.body);
    check(token, { 'orders/create token extracted': (t) => t !== null });

    const address = firstOptionValueBySelectId(createGet.body, "addressSelect");
    const delivery = firstOptionValueBySelectId(createGet.body, "deliveryTimeSelect");

    check(address, { 'address option exists': (x) => x !== null });
    check(delivery, { 'delivery option exists': (x) => x !== null });

    if (!address || !delivery) {
        sleep(1);
        return;
    }

    const payload = formEncode({
        'PostModel.Address': address,
        'PostModel.DeliveryTime': delivery,
        __RequestVerificationToken: token,
    });

    const post = http.post(`${BASE_URL}/Orders/Create`, payload, {
        redirects: 0,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    check(post, { 'order create redirect 302': (r) => r.status === 302 });
}

export function setup() {
    // создаём пользователей заранее (чтобы VU не делили одну корзину)
    const users = [];
    const stamp = Date.now();

    for (let i = 0; i < USER_COUNT; i++) {
        const email = `load_${stamp}_${i}@test.local`;
        const password = `P@ssw0rd_${stamp}_${i}`;
        registerUser(email, password);
        users.push({ email, password });
    }
    return { users };
}

export default function (data) {
    const u = data.users[(__VU - 1) % data.users.length];

    group('checkout flow', () => {
        login(u.email, u.password);

        // адрес добавляем один раз в начале “жизни” пользователя — но для простоты можно держать так:
        ensureAddress();

        const menu = http.get(`${BASE_URL}/Menu/Index`);
        check(menu, { 'menu 200': (r) => r.status === 200 });

        check(menu, { 'menu has AddToCart button': (r) => r.body.includes('AddToCart') });

        const addUrl = pickFirstAddToCartUrl(menu.body);
        check(addUrl, { 'found AddToCart link': (x) => x !== null });

        if (!addUrl) {
            // чтобы не падало TypeError и прогон продолжался корректно
            sleep(1);
            return;
        }

        addToCart(addUrl);

        const cart = http.get(`${BASE_URL}/Cart/Index`);
        check(cart, { 'cart 200': (r) => r.status === 200 });

        createOrder();

        const orders = http.get(`${BASE_URL}/Orders/Index`);
        check(orders, { 'orders page 200': (r) => r.status === 200 });
    });

    sleep(1);
}