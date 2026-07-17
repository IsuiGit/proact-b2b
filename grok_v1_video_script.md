# PROACT B2B — Сценарий видео для Grok V1

## Технические параметры

| Параметр | Значение |
|----------|----------|
| Модель | `grok-imagine-video` (Grok V1) |
| Максимум на клип | 15 секунд |
| Разрешение | 720p |
| Соотношение | 16:9 |
| Всего клипов | 8 |
| Общая длительность | ~95 секунд (1:35) |
| Язык | Русский (оверлей + закадровый) |

## Стратегия

Grok V1 хорошо генерирует кинематографичные сцены, движение, атмосферу.
Плохо — текст, UI, таблицы, код.

Поэтому:
- **Визуал** — метафорические и драматические сцены (промпты на английском, т.к. модель лучше понимает)
- **Русский текст** — наложение в пост-продакшене (After Effects / DaVinci / CapCut)
- **Закадровый голос** — отдельная запись на русском, накладывается на смонтированный видеоряд
- **Склейка** — ffmpeg concat: `ffmpeg -f concat -i clips.txt -c copy final.mp4`

---

## Клип 1: Проблема (0:00 — 0:10, 10 сек)

### Grok V1 Prompt
```
A dark, chaotic office at night. A stressed businessman sits at a desk buried under thousands of scattered documents and glowing data screens. The camera slowly pushes in from behind, over his shoulder, revealing an overwhelming wall of unorganized information. Papers float in the air. The mood is oppressive, claustrophobic. Cold blue lighting with harsh shadows. Cinematic, shallow depth of field.
```

### Russian voiceover
> Десять тысяч компаний. Каждый день — новые события, контракты, регистрации. Ваш менеджер проверяет пять. Остальные — упущенные возможности.

### Russian text overlay
```
[0:02 — 0:05] "10 000 компаний"
[0:05 — 0:08] "5 проверяет менеджер"
[0:08 — 0:10] "9 995 — упущены"
```

### Notes
- Ощущение хаоса и перегруза
- Тёмная гамма → переход к светлой в следующем клипе

---

## Клип 2: Решение (0:10 — 0:20, 10 сек)

### Grok V1 Prompt
```
A clean, bright modern workspace. A single laptop on a minimalist desk. The screen illuminates the room with warm golden light. A hand types a single command. The camera sweeps around the desk in a smooth 180-degree arc. Dust particles float in the warm light beam. The atmosphere shifts from dark to bright, hopeful, empowering. 35mm lens, golden hour lighting through window.
```

### Russian voiceover
> Одна команда. Одна система. От хаоса — к готовым клиентам.

### Russian text overlay
```
[0:12 — 0:16] /pipeline --smart
[0:16 — 0:20] "SCOUT → ANALYST → WARMUP → BRIEF → TRACKER"
```

### Notes
- Резкий контраст с Клипом 1: тьма → свет
- Пробуждение, решение приходит

---

## Клип 3: SCOUT (0:20 — 0:35, 15 сек)

### Grok V1 Prompt
```
Abstract data visualization scene. Thousands of glowing golden particles stream from multiple directions — like rivers of light converging into a single bright vortex. As the vortex spins, particles sort themselves: most fade away, while the brightest fifty remain orbiting in a structured formation. The camera slowly zooms into the vortex center. Dark background with deep space feel. The brightest particles pulse with warm amber light. Cinematic particle simulation, volumetric lighting.
```

### Russian voiceover
> SCOUT собирает события из десяти источников. Пятьсот восемьдесят восемь сигналов фильтруются по весу: давность, вероятность, маржа. На выходе — пятьдесят лучших.

### Russian text overlay
```
[0:22 — 0:25] "SCOUT — 10 источников"
[0:25 — 0:28] "588 событий"
[0:28 — 0:32] "→ 50 по весу"
[0:32 — 0:35] "Rosneft 9.3 · Aeroflot 8.9 · FSK 8.4"
```

### Notes
- Самый длинный клип — даём SCOUT время
- Частицы = события, яркие = отфильтрованные топ-50
- Можно добавить реальные цифры из последнего пайплайна

---

## Клип 4: ANALYST (0:35 — 0:50, 15 сек)

### Grok V1 Prompt
```
A futuristic holographic dashboard floating in mid-air. Multiple translucent panels materialize one by one, each showing abstract data rings and percentage indicators that pulse and lock into place. A camera slowly orbits the dashboard. The panels are color-coded: green for low risk, amber for medium. One panel has a small red badge that morphs into a green checkmark — representing system learning from past contact. Dark tech environment with holographic blue-amber glow. Sci-fi corporate aesthetic, clean and precise.
```

### Russian voiceover
> ANALYST оценивает риск, строит продуктовую матрицу и считает confidence. Девяносто три процента по Роснефти. Восемьдесят девять по Аэрофлоту — с пометкой «был контакт, отклонил аргумент». Система помнит и учится.

### Russian text overlay
```
[0:37 — 0:42] "ANALYST — риск + продукты"
[0:42 — 0:46] "Роснефть 93% · Аэрофлот 89%"
[0:46 — 0:50] "⚠ был контакт → новый аргумент"
```

### Notes
- Голографические панели = аналитические карточки
- Красный → зелёный бейдж = самообучение (киллер-фича)

---

## Клип 5: WARMUP (0:50 — 1:05, 15 сек)

### Grok V1 Prompt
```
A split-screen scene. Left side: a golden balance scale tipping, coins flowing from one pan to another — representing rate discount on one side, cross-sell commission income on the other, reaching equilibrium. Right side: a beautifully composed email materializing letter by letter on a sleek dark interface. The camera slowly pushes in on the balance scale. Warm cinematic lighting, shallow depth of field. The scale finds perfect balance — the moment of equilibrium is emphasized with a gentle light pulse. Luxury financial aesthetic.
```

### Russian voiceover
> WARMUP пишет персональное письмо. Не «у нас дешевле», а пакет: ставка на ноль целых три десятых ниже — компенсируется кросс-продажей. ВЭД, эквайринг, зарплатный проект. Без кросс-продукта ставку не упоминаем. Это не скидка — это бизнес-логика.

### Russian text overlay
```
[0:52 — 0:56] "WARMUP — персональное письмо"
[0:56 — 1:00] "ставка ↓0.3% = комиссии ↑0.3%"
[1:00 — 1:05] "Не скидка. Пакет."
```

### Notes
- Весы = ключевая визуальная метафора всей концепции
- Равновесие = окупаемость пакета
- Самый важный продающий момент

---

## Клип 6: BRIEF (1:05 — 1:15, 10 сек)

### Grok V1 Prompt
```
A smartphone held in a hand, screen facing camera. On the screen, a sleek dark dashboard with glowing cards and data visualizations slides smoothly as a thumb scrolls. The camera tracks the scrolling motion. Background: a blurred corporate lobby with glass walls. The phone screen light illuminates the holder's face subtly. Modern, professional, the feeling of walking into a meeting fully prepared. Warm interior lighting, shallow depth of field.
```

### Russian voiceover
> BRIEF — интерактивное досье на телефон. Точка входа, риски, финансовая динамика, план звонка, ответы на возражения. Заходите на встречу во всеоружии.

### Russian text overlay
```
[1:07 — 1:10] "BRIEF — досье на телефон"
[1:10 — 1:15] "План звонка · Возражения · Чек-лист"
```

### Notes
- Телефон = мобильность, готовность
- Лобби = контекст встречи

---

## Клип 7: TRACKER + цикл обучения (1:15 — 1:25, 10 сек)

### Grok V1 Prompt
```
A circular flow diagram made of glowing light paths, rotating slowly in 3D space. Five nodes connected in a loop: data streams flow from one node to the next, completing the circuit. At one node, a pulse of red light (feedback) travels backwards through the loop, transforming into green as it reaches the start — the system adapts. The camera pulls back to reveal the full cycle. Dark tech background with amber and green light trails. Motion graphics style, precise and satisfying.
```

### Russian voiceover
> TRACKER фиксирует результат. Отказ — анализируем — корректируем аргументы — следующий прогон умнее. /pipeline --learn. Замкнутый цикл.

### Russian text overlay
```
[1:17 — 1:20] "TRACKER — воронка"
[1:20 — 1:25] "Отказ → learn → новый аргумент"
```

### Notes
- Круговой цикл = замкнутость системы
- Красный → зелёный = обучение на отказах

---

## Клип 8: Финал (1:25 — 1:35, 10 сек)

### Grok V1 Prompt
```
A rapid cinematic montage transitioning through multiple scenes: scattered particles organizing into structure, balance scales reaching equilibrium, a phone screen lighting up, a circular loop completing. All elements converge into a single bright point of light that explodes into a clean dark background with a subtle logo placeholder. Epic, satisfying resolution. The camera pulls back to reveal emptiness with one glowing element remaining. Dramatic final beat, premium product reveal aesthetic.
```

### Russian voiceover
> От пятисот восьмидесяти восьми сигналов — до пяти готовых клиентов. Одна команда. PROACT.

### Russian text overlay
```
[1:27 — 1:30] "588 сигналов → 5 клиентов"
[1:30 — 1:33] "Одна команда"
[1:33 — 1:35] "PROACT"
```

### Notes
- Нарезка всех ключевых визуалов = целостность
- Логотип — наложить в пост-продакшене (Grok не нарисует логотип)

---

## Инструкция по сборке

### Шаг 1: Генерация клипов через Grok V1 API

Для каждого клипа отправить запрос:
```json
{
  "model": "grok-imagine-video",
  "prompt": "<промпт из клипа>",
  "duration": <10 или 15>,
  "aspect_ratio": "16:9",
  "resolution": "720p"
}
```

Альтернатива — через веб-интерфейс Grok Imagine, вставляя каждый промпт вручную.

### Шаг 2: Закадровый голос

Записать русскую начитку (8 отрывков) отдельно.
Рекомендуемый голос: мужской, уверенный, темп средний.
Или TTS: Silero TTS / Yandex SpeechKit на русском.

### Шаг 3: Текстовые оверлеи

Наложить русский текст (тайминги указаны для каждого клипа) в видеоредакторе:
- Шрифт: Montserrat Bold / Inter Bold
- Цвет: белый с лёгким свечением
- Позиция: нижняя треть или центр

### Шаг 4: Склейка

```bash
# Создать файл clips.txt
file 'clip1.mp4'
file 'clip2.mp4'
file 'clip3.mp4'
file 'clip4.mp4'
file 'clip5.mp4'
file 'clip6.mp4'
file 'clip7.mp4'
file 'clip8.mp4'

# Склеить
ffmpeg -f concat -safe 0 -i clips.txt -c copy proact_demo.mp4

# Наложить аудиодорожку
ffmpeg -i proact_demo.mp4 -i voiceover.wav -c:v copy -c:a aac -shortest proact_final.mp4
```

### Шаг 5: Альтернатива — Video Extension API

Вместо склейки можно продлевать ключевые клипы через extension:
```
POST /v1/videos/extensions
{ "request_id": "<clip3_id>", "duration": 5 }
```
Это даст плавный переход вместо резкого cut. Но работает только для продления, не для перехода между разными сценами.

---

## Сводка клипов

| # | Время | Длительность | Сцена | Ключевая метафора |
|---|-------|-------------|-------|-------------------|
| 1 | 0:00 | 10s | Проблема | Хаос, перегруз |
| 2 | 0:10 | 10s | Решение | Тьма → свет, одна команда |
| 3 | 0:20 | 15s | SCOUT | Частицы → вихрь → топ-50 |
| 4 | 0:35 | 15s | ANALYST | Голографический дашборд |
| 5 | 0:50 | 15s | WARMUP | Весы: ставка ↔ комиссии |
| 6 | 1:05 | 10s | BRIEF | Телефон с досье |
| 7 | 1:15 | 10s | TRACKER | Замкнутый цикл |
| 8 | 1:25 | 10s | Финал | Нарезка → логотип |

**Итого: 95 секунд, 8 клипов Grok V1 + 1 аудиодорожка + текстовые оверлеи.**
