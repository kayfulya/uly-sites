// ===== данные =====
const SPEECHES = {
  'no-date': ['Лёш, ну', 'куда', 'не-не-не', 'ну ты чё', 'передумай'],
  'no-pay':  ['член большой — управляй мечтой', 'Алексей Андреевич!'],
};

const STATE = {
  attempts: 0,
  currentSceneKey: 'date',
};

// ===== утилиты =====
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const rand = (min, max) => Math.random() * (max - min) + min;

function isTouch() {
  return matchMedia('(hover: none)').matches;
}

// показать речевое облачко на текущей сцене
function speak(text) {
  const scene = $(`.scene[data-scene="${STATE.currentSceneKey}"]`);
  if (!scene) return;
  const bubble = $('[data-speech]', scene);
  if (!bubble) return;
  bubble.textContent = text;
  bubble.classList.add('is-visible');
  clearTimeout(bubble._t);
  bubble._t = setTimeout(() => bubble.classList.remove('is-visible'), 1400);
}

// ===== убегающая кнопка =====
function setupRunaway(btn) {
  const key = btn.dataset.runaway;
  let speechIdx = 0;
  let attempts = 0;

  // стартовая позиция: внутри своего .buttons-контейнера
  // но при первом «приближении» — становится fixed и прыгает
  let positioned = false;

  function teleport() {
    if (!positioned) {
      btn.style.position = 'fixed';
      positioned = true;
    }
    const w = window.innerWidth;
    const h = window.innerHeight;
    const rect = btn.getBoundingClientRect();
    const margin = 20;
    const newLeft = rand(margin, w - rect.width  - margin);
    const newTop  = rand(margin + 80, h - rect.height - margin - 80);
    btn.style.left = `${newLeft}px`;
    btn.style.top  = `${newTop}px`;
    btn.style.transform = `rotate(${rand(-12, 12)}deg)`;

    // комментарий белки
    const list = SPEECHES[key] || [];
    if (list.length) {
      speak(list[speechIdx % list.length]);
      speechIdx++;
    }

    // счётчик
    attempts++;
    STATE.attempts++;
    if (attempts >= 5) {
      btn.classList.add('is-tiny');
    }
  }

  // десктоп: ловим mousemove, прыгаем при сближении
  document.addEventListener('mousemove', (e) => {
    if (btn.offsetParent === null && positioned === false) return; // скрытая сцена
    const r = btn.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top  + r.height / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;
    const dist = Math.hypot(dx, dy);
    if (dist < 110) teleport();
  });

  // мобайл: автопрыжки + телепорт при тапе
  if (isTouch()) {
    btn.addEventListener('touchstart', (e) => {
      e.preventDefault();
      teleport();
    }, { passive: false });

    // автопрыжки только если кнопка в активной сцене
    setInterval(() => {
      const scene = btn.closest('.scene');
      if (!scene || scene.hasAttribute('hidden')) return;
      teleport();
    }, 1300);
  }

  // на всякий клик — тоже не проходит
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    teleport();
  });
}

// ===== переключение сцен =====
function showScene(key) {
  $$('.scene').forEach(s => s.toggleAttribute('hidden', s.dataset.scene !== key));
  STATE.currentSceneKey = key;
  window.scrollTo(0, 0);
}

// ===== обработчики «Да» =====
function setupYes() {
  $('[data-action="yes-date"]').addEventListener('click', () => {
    speak('как нам с тобой вдвоём хорошо…');
    setTimeout(() => showScene('pay'), 600);
  });

  $('[data-action="yes-pay"]').addEventListener('click', () => {
    showScene('final');
    runConfetti();
    $('[data-attempts]').textContent = STATE.attempts;
  });
}

// ===== конфетти из сердечек =====
function runConfetti() {
  if (typeof confetti !== 'function') return;
  const end = Date.now() + 2500;
  const colors = ['#8a1f3d', '#c8365f', '#f4a8b8', '#d4a14e', '#fef0e0'];

  (function frame() {
    confetti({
      particleCount: 4,
      angle: 60,
      spread: 70,
      origin: { x: 0, y: 0.7 },
      colors,
      scalar: 1.2,
      shapes: ['circle'],
    });
    confetti({
      particleCount: 4,
      angle: 120,
      spread: 70,
      origin: { x: 1, y: 0.7 },
      colors,
      scalar: 1.2,
      shapes: ['circle'],
    });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();

  // дополнительный финальный залп
  setTimeout(() => {
    confetti({
      particleCount: 120,
      spread: 100,
      origin: { y: 0.5 },
      colors,
      scalar: 1.4,
    });
  }, 600);
}

// ===== старт =====
document.addEventListener('DOMContentLoaded', () => {
  $$('[data-runaway]').forEach(setupRunaway);
  setupYes();
  setTimeout(() => speak('привет 💕'), 800);
});
