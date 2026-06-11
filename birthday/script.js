// ============ Анонимное бронирование через JSONBin ============
// Состояние массив { reserved: ['id1', 'id2', ...] } — кто кто, не знаем.
// Кнопка «Это я» работает только у того гостя, что бронировал (по localStorage).

const STORAGE_KEY = 'wishlist:mine';
const BIN_BASE = `https://api.jsonbin.io/v3/b/${JSONBIN_ID}`;

const State = {
  reserved: new Set(),
  mine: new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')),
};

async function fetchReserved() {
  try {
    const res = await fetch(`${BIN_BASE}/latest`, {
      headers: { 'X-Master-Key': JSONBIN_KEY },
      cache: 'no-store',
    });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    const arr = (data.record && data.record.reserved) || [];
    return Array.isArray(arr) ? arr : [];
  } catch (e) {
    console.error('JSONBin read:', e);
    return [];
  }
}

async function pushReserved() {
  try {
    const res = await fetch(BIN_BASE, {
      method: 'PUT',
      headers: { 'X-Master-Key': JSONBIN_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ reserved: [...State.reserved] }),
    });
    return res.ok;
  } catch (e) {
    console.error('JSONBin write:', e);
    return false;
  }
}

function saveMine() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...State.mine]));
}

// ============ Рендер ============

const TYPE_CHIP = {
  gift: null,
  collect: { cls: 'wish__chip--collect', label: 'сбор' },
  experience: { cls: 'wish__chip--exp', label: 'впечатление' },
  sweet: { cls: 'wish__chip--sweet', label: 'просто так' },
  social: { cls: 'wish__chip--social', label: 'в инсте' },
};

function fmtMoney(n) { return n.toLocaleString('ru-RU') + ' ₽'; }

function linkHost(url) {
  if (!url) return 'ссылку';
  if (url.includes('wildberries')) return 'Wildberries';
  if (url.includes('bubnovsky')) return 'центр Бубновского';
  if (url.includes('vintagedresses')) return 'VintageDresses';
  if (url.includes('primuladesign')) return 'Primula Design';
  if (url.includes('thesweetsetup')) return 'обзор-пример';
  return 'сайт';
}

function renderReserveBtn(wish) {
  const isReserved = State.reserved.has(wish.id);
  const isMine = State.mine.has(wish.id);
  if (isReserved && isMine) return `<button class="btn btn--reserved" data-toggle="${wish.id}">Это я · снять</button>`;
  if (isReserved) return `<button class="btn btn--disabled" disabled>Уже занято</button>`;
  return `<button class="btn" data-toggle="${wish.id}">Забронировать</button>`;
}

function renderAction(wish) {
  if (wish.type === 'collect') {
    return `<a class="btn" href="${wish.payment.url}" target="_blank" rel="noopener">Перевести → ${wish.payment.method}</a>`;
  }
  if (wish.type === 'sweet') return `<p class="wish__hint">Без брони, сколько угодно.</p>`;
  if (wish.type === 'social') return `<p class="wish__hint">Без брони — можно вместе.</p>`;
  if (wish.reservable === false) return `<p class="wish__hint">Без брони, сколько угодно.</p>`;
  return renderReserveBtn(wish);
}

function renderMeta(wish) {
  const bits = [];
  if (wish.price) bits.push(`<span class="wish__price">${wish.price}</span>`);
  if (wish.link) bits.push(`<a class="wish__link" href="${wish.link}" target="_blank" rel="noopener">Открыть на ${linkHost(wish.link)} →</a>`);
  if (!bits.length) return '';
  return `<div class="wish__meta">${bits.join('')}</div>`;
}

function renderWish(wish, idx) {
  const num = String(idx + 1).padStart(2, '0');
  const chip = TYPE_CHIP[wish.type];
  const chipHtml = chip ? `<span class="wish__chip ${chip.cls}">${chip.label}</span>` : '';
  const subHtml = wish.subtitle ? `<span class="wish__sub">${wish.subtitle}</span>` : '';
  const noteHtml = wish.note ? `<p class="wish__note">«${wish.note}»</p>` : '';
  const mediaHtml = wish.image
    ? `<div class="wish__media"><img src="${wish.image}" alt="${wish.title}" loading="lazy"></div>`
    : '';
  const classes = ['wish'];
  if (wish.image) classes.push('wish--with-media');
  if (wish.favorite) classes.push('wish--favorite');

  return `
    <li class="${classes.join(' ')}" id="wish-${wish.id}">
      <div class="wish__num">${num}</div>
      <div class="wish__body">
        ${mediaHtml}
        <div class="wish__text">
          ${chipHtml}
          <h3 class="wish__title">${wish.title}</h3>
          ${subHtml}
          ${noteHtml}
          ${renderMeta(wish)}
        </div>
      </div>
      <div class="wish__action" data-action="${wish.id}">
        ${renderAction(wish)}
      </div>
    </li>
  `;
}

function renderAll() {
  const wishesEl = document.getElementById('wishes');
  const favorites = WISHES.filter(w => w.favorite);
  const rest = WISHES.filter(w => !w.favorite);

  let html = '';
  if (favorites.length) {
    html += `<li class="wishes__section"><h2 class="wishes__section-title">Очень хочу!</h2></li>`;
    html += favorites.map((w, i) => renderWish(w, i)).join('');
  }
  if (rest.length) {
    html += `<li class="wishes__section wishes__section--soft"><h2 class="wishes__section-title">По вашему желанию</h2></li>`;
    html += rest.map((w, i) => renderWish(w, favorites.length + i)).join('');
  }
  wishesEl.innerHTML = html;
  document.getElementById('count').textContent = WISHES.length;
}

function refreshActionFor(wishId) {
  const wish = WISHES.find(w => w.id === wishId);
  if (!wish) return;
  const el = document.querySelector(`[data-action="${wishId}"]`);
  if (!el) return;
  el.innerHTML = renderAction(wish);
}

// ============ Бронирование ============

async function toggleReservation(wishId, btn) {
  btn.classList.add('btn--loading');
  const wasReserved = State.reserved.has(wishId);
  if (wasReserved && !State.mine.has(wishId)) { btn.classList.remove('btn--loading'); return; }

  if (wasReserved) { State.reserved.delete(wishId); State.mine.delete(wishId); }
  else { State.reserved.add(wishId); State.mine.add(wishId); }
  refreshActionFor(wishId);

  const ok = await pushReserved();
  if (!ok) {
    if (wasReserved) { State.reserved.add(wishId); State.mine.add(wishId); }
    else { State.reserved.delete(wishId); State.mine.delete(wishId); }
    refreshActionFor(wishId);
    alert('Не удалось сохранить. Попробуй ещё раз через минуту.');
    return;
  }
  saveMine();
}

// ============ Старт ============

document.addEventListener('click', (e) => {
  const toggle = e.target.closest('[data-toggle]');
  if (toggle) toggleReservation(toggle.dataset.toggle, toggle);
});

(async function init() {
  renderAll();
  const arr = await fetchReserved();
  State.reserved = new Set(arr);
  WISHES.filter(w => w.reservable).forEach(w => refreshActionFor(w.id));
})();
