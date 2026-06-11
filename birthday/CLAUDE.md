# Birthday-Wishlist — вишлист Ули ко дню рождения

## Главное
- День рождения **27 мая 2026** (совпадает с днём города Санкт-Петербурга)
- Уле **26 лет**
- Live: **https://kayfulya.github.io/birthday/**
- Репо: **kayfulya/birthday** (public), gh CLI авторизован под kayfulya
- Тон: лёгкий, петербургский, с характером, не «милый-розовый»
- Слово «хочулик» — её. Везде «хочулики», не «пункты», не «подарки»

## Архитектура
- **Чистый HTML/CSS/JS**, без сборки, без npm
- Бронирование: **JSONBin.io** — CORS-friendly, ключи (BIN_ID + MASTER_KEY) в `data.js`
- Сборы (лечение/кейп/пальто): общий URL Т-Банк → `https://www.tbank.ru/cf/4cS9QDSyPTm`
- Деплой: GitHub Pages (автообновление при push в main)

## Файлы
- `index.html` — структура
- `styles.css` — стили (палитра в `:root`)
- `data.js` — массив `WISHES` + `JSONBIN_ID` + `JSONBIN_KEY`
- `script.js` — рендер + JSONBin GET/PUT
- `assets/` — фото и SVG
- `squirrels.html` — галерея 10 белок (sq-1…sq-10.svg) для выбора

## Палитра (`:root` в styles.css)
- bg `#f3ede2` (кремовая бумага)
- ink `#1c1c1c` (графит)
- accent `#b8431f` (терракот, питерский фасад)
- moss `#5d6b5b` (мшистый зелёный)
- Шрифты: **Cormorant Garamond** (заголовки, курсив) + **Inter** (тело)

## Контент-правила (важно при правках)
- Подпись в footer — **«Имбуля»** (не «рилсуля»)
- WhatsApp **не использовать** — Уля сказала «никто им не пользуется»
- Маленькие хочулики (компактные чипы) **убраны** — она их назвала «дурацкими»
- Тату «Люблю Улю» **убран целиком**
- На сборах **нет прогресс-бара** — кнопка ведёт прямо на Т-Банк (он сам показывает сумму)
- Голос в подписях: «Сколько хош!», «Очки уважения!», «Способ избегания реальности!» — прямой, образный

## Список хочуликов (16 шт, см. data.js)
**Очень хочу! (favorite: true):**
1. Поцелуи в щёчку (sweet)
2. Сторис обо мне (social)
3. Танец робота-паука! (sweet)
4. Сводить меня в Ботанический сад (experience)
5. Кепка «кайфуля» (gift)
6. Открытка от руки (gift)

**По вашему желанию:**
- Сбор на лечение (collect, 30к)
- Кейп с капюшоном (collect, 28к)
- Пальто-трапеция (collect, 37,5к)
- Солнцезащитный стик TOCOBO (sweet, без брони)
- Перья в волосы (sweet, без брони)
- Коридор · Тарелки Lefard · Блузка PARA SLOW · Книга Грегори · Литрес · Очки · Верёвочный парк

## SVG-картинки (рисовала вручную в стиле сайта)
`cap.svg`, `tattoo.svg` (не используется, файл остался), `reab.jpg` (фото шрама), `stories.svg`, `litres.svg`, `shades.svg`, `rope-park.svg`, `spider-robot.svg`, `botsad.svg`, `squirrel.svg`, `assets/squirrels/sq-1.svg`…`sq-10.svg`

## Бронирование (логика script.js)
- При загрузке: GET `https://api.jsonbin.io/v3/b/{ID}/latest` → `reserved: [...]`
- Клик «Забронировать» → добавляет id в массив, PUT в бин, сохраняет в `localStorage` (свой)
- Клик «Это я · снять» (только для своих по localStorage) → удаляет из бина
- Чужая бронь → «Уже занято», disabled
- **Анонимно**: Уля не видит кто, видит только статус занято/свободно

## Что сделать в новом чате (TODO)
- Уля должна выбрать одну белку из 10 (открыть `squirrels.html` локально, она скажет номер). Сейчас на сайте `squirrel.svg` (=sq-1)
- Возможны новые хочулики, правки текстов, замены фото

## Полезные команды
```bash
# Скриншот сайта в headless Chrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --hide-scrollbars \
  --window-size=1400,5200 --screenshot=/tmp/wl.png \
  file:///Users/ula/Documents/Personal/Birthday-Wishlist/index.html

# Картинки с Wildberries (basket lookup)
NM=160847016; VOL=$((NM/100000)); PART=$((NM/1000))
for b in 09 10 11 12 13 14 15; do
  curl -sSf -o spf.webp "https://basket-${b}.wbbasket.ru/vol${VOL}/part${PART}/${NM}/images/big/1.webp" && echo "basket=$b" && break
done

# Деплой
git add . && git commit -m "..." && git push
# GitHub Pages обновится сам через 30-60 сек
```

## Что НЕ светить
- JSONBIN_KEY уже в публичном data.js на GitHub — это сознательное решение Ули.
  Если кто-то будет вандалить — создадим Access Key вместо Master Key (правит только этот бин)
