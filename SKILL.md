---
name: exton-wallet
description: Manage Exton TON crypto wallet — send TON/jettons, manage plugins (whitelist, daily-limit, subscriptions, payroll), sign transactions via Keystone 3 Pro QR.
metadata: {"openclaw":{"requires":{"bins":["python3"]},"emoji":"💎","os":["darwin","linux"],"install":[{"id":"deps","kind":"download","label":"Install Exton dependencies","bins":["python3"],"command":"bash {baseDir}/scripts/install.sh"}]}}
---

# Exton Wallet Skill

Управление криптокошельком Exton на блокчейне TON. Приватный ключ никогда не покидает аппаратный кошелёк Keystone 3 Pro.

## Когда использовать

Пользователь просит: создать кошелёк, баланс, отправить TON/токены/NFT, проверить лимиты, историю транзакций, резолвить .ton домен.

## Создание нового кошелька

Когда пользователь хочет создать новый Exton MultiSig кошелёк:

1. Попросить: "Откройте Keystone 3 Pro → выберите Tonkeeper → покажите QR-код. Сфотографируйте и отправьте фото в чат."
2. Когда пользователь пришлёт фото QR:
   ```
   exec: bash {baseDir}/scripts/run.sh create-wallet --photo <path_to_photo>
   ```
3. Из JSON ответа показать пользователю:
   - Адрес кошелька (`wallet_address`)
   - Recovery Code (`recovery_code`) — **ОБЯЗАТЕЛЬНО** предупредить:
     "⚠️ СОХРАНИТЕ Recovery Code! Это единственный способ восстановить кошелёк.
      Запишите на бумаге и храните в надёжном месте. Не делайте скриншот."
4. Кошелёк автоматически настроен для отправки через этот skill.

## Подключение существующего кошелька

Если файл `~/.exton/config.json` не существует и у пользователя УЖЕ есть кошелёк:

1. Спросить: "Введите Recovery Code вашего Exton MultiSig кошелька (71 символ)"
2. Запустить:
   ```
   exec: bash {baseDir}/scripts/run.sh setup --recovery-code "<code>"
   ```
4. Из ответа JSON взять `wallet_address` и сообщить:
   "✅ Кошелёк подключён: <wallet_address>"
   Затем показать баланс:
   ```
   exec: bash {baseDir}/scripts/run.sh balance
   ```

ВАЖНО: Recovery Code содержит секретные данные. НИКОГДА не логировать, не показывать,
не сохранять его в чат-историю. После setup код больше не нужен.

## Чтение (без подписи, без ключей)

### Баланс
```
exec: bash {baseDir}/scripts/run.sh balance
```
Ответ JSON: `{balance_nano, balance_ton, status}`

### История транзакций
```
exec: bash {baseDir}/scripts/run.sh history --limit 20
```

### Резолв .ton домена
```
exec: bash {baseDir}/scripts/run.sh resolve <domain.ton>
```
Ответ JSON: `{domain, address}`

### Jetton-балансы (USDT и др.)
```
exec: bash {baseDir}/scripts/run.sh jettons
```

### Текущий seqno
```
exec: bash {baseDir}/scripts/run.sh seqno
```

### Проверка новых транзакций
```
exec: bash {baseDir}/scripts/run.sh watch
```
Возвращает JSON: `new_incoming`, `new_outgoing`, `has_new`, `balance_ton`.
Помнит последнюю проверку — показывает только НОВЫЕ транзакции.
Если `has_new` = true → уведомить пользователя о каждой транзакции.
Если `has_new` = false → ничего не делать.

### Проверка последних транзакций (без фильтра)
```
exec: bash {baseDir}/scripts/run.sh check-tx
```

### Плагины и лимиты
```
exec: bash {baseDir}/scripts/run.sh plugins list
exec: bash {baseDir}/scripts/run.sh plugins limits
```

## Отправка TON

### Два режима

**Режим 1: Через плагин (автоматически, если адрес в whitelist и в пределах лимита)**
Не требует Keystone подпись. Агент подписывает exton_app_key автоматически.

**Режим 2: Прямой перевод (с Keystone QR)**
Требует физическую подпись на Keystone 3 Pro.

### Алгоритм принятия решения

1. Проверить: есть ли whitelist плагин?
2. Если да — проверить адрес в whitelist через GET-метод
3. Проверить daily-limit: remainingToday() >= amount?
4. Если оба ✓ → Режим 1 (автоматически)
5. Иначе → Режим 2 (QR + Keystone)

### Режим 2: QR-подпись через чат (Telegram/WhatsApp/Discord)

Весь flow происходит В ЧАТЕ — QR отправляется как картинка, подпись приходит как фото.

**Шаг 1: Построить TX и получить QR**
```
exec: bash {baseDir}/scripts/run.sh send --to <address> --amount <nanotons> [--comment "..."]
```
Вернёт JSON с полем `qr_image_base64` — это PNG картинка в base64.

**Шаг 2: QR отправляется автоматически**
Команда send сама отправляет QR-картинку в чат через `openclaw message send --media`.
Ты НЕ должен отправлять QR — скрипт делает это сам.
Просто сообщи пользователю что QR отправлен и жди фото подписи.

**Шаг 3: Получить фото подписи от пользователя**
Пользователь отправляет ФОТО экрана Keystone с QR подписи.
Сохранить фото в файл, затем:
```
exec: bash {baseDir}/scripts/run.sh sign-submit --photo <path_to_photo>
```
→ Декодирует QR из фото → извлекает Ed25519 подпись → собирает signed BOC → broadcast в TON

**Шаг 4: Подтвердить результат**
"✅ Транзакция отправлена!
Сумма: 50 TON
Получатель: wallet.ton (UQx...)
Hash: abc123..."

ВАЖНО: Между шагом 2 и 3 ждать ответа пользователя. НЕ продолжать без фото подписи.

**Шаг 5: Подтверждение**
Команда sign-submit автоматически ждёт подтверждения (до 60 секунд).
Если `status` = `confirmed` — сообщить пользователю:
"✅ Транзакция подтверждена! Баланс: X TON"
Если `status` = `broadcast` — сообщить:
"Транзакция отправлена, ожидает подтверждения в сети TON."

## Проверка транзакций (входящие/исходящие)

Когда пользователь спрашивает "пришли ли деньги?", "что с переводом?", "баланс обновился?":
```
exec: bash {baseDir}/scripts/run.sh check-tx
```
Вернёт JSON с последними входящими и исходящими транзакциями + текущий баланс.
Агент должен красиво отформатировать ответ:
- Входящие: "Получено X TON от адреса..."
- Исходящие: "Отправлено X TON на адрес..."
- Текущий баланс

4. Подтвердить результат.

## Мониторинг входящих транзакций

Команда `watch` проверяет новые транзакции с момента последней проверки:
```
exec: bash {baseDir}/scripts/run.sh watch
```
Возвращает JSON с полями `new_incoming`, `new_outgoing`, `has_new`, `balance_ton`.

Если `has_new` = true, уведомить пользователя:
- Входящие: "💰 Получено X TON от UQabc..."
- Исходящие: "📤 Отправлено X TON на UQxyz..."
- Текущий баланс

Если `has_new` = false — НЕ отправлять ничего, молча завершить.

Мониторинг работает автоматически — системный cron каждую минуту проверяет новые
транзакции и отправляет уведомление в Telegram. Настраивается при install.sh, 
пользователю ничего делать не нужно. Расход AI-токенов: ноль.

## Обновление

Если пользователь сообщает о проблеме или просит обновить:
```
exec: bash {baseDir}/scripts/update.sh
```
Это обновит skill до последней версии с GitHub и перезапустит Gateway.

## Безопасность

- НИКОГДА не показывать содержимое `~/.exton/app_key.enc`
- НИКОГДА не выводить приватные ключи или Recovery Code в чат
- НИКОГДА не отправлять Recovery Code по сети
- Для операций вне плагинов ВСЕГДА требовать QR-подпись Keystone
- При ошибке подписи — НЕ повторять, сообщить пользователю
- Плагины работают в рамках on-chain constraints — это НЕЛЬЗЯ обойти
- Whitelist: только заранее одобренные адреса (on-chain dict)
- Daily Limit: максимум N TON за 24 часа (on-chain counter с auto-reset)

## Доступные плагины

| Плагин | Назначение | Trigger |
|--------|-----------|---------|
| whitelist | Только одобренные адреса | Owner |
| daily-limit | Макс N TON/сутки | Owner |
| subscription | Регулярный фиксированный платёж | Anyone (по времени) |
| payroll | Зарплаты команде | Anyone (по времени) |
| timelock | Разовый платёж по дате | Anyone (по времени) |
| inheritance | Всё бенефициару при неактивности | Anyone / Owner (ping) |
| dead-man-switch | Распределение по % при неактивности | Anyone / Owner (ping) |
| domain-renewal | Продление .ton доменов | Anyone (по времени) |
| auto-swap | Jetton → TON через DEX | Owner |
| staking-manager | Авто-стейкинг по порогам | Owner |
| split-payment | Распределение суммы по % | Owner |
