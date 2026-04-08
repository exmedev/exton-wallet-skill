# Exton Wallet — OpenClaw Skill

Управляй криптокошельком Exton на TON через AI-агента. Приватный ключ никогда не покидает аппаратный кошелёк Keystone 3 Pro.

## Установка

```bash
git clone https://github.com/exmedev/exton-wallet-skill.git \
  ~/.openclaw/skills/exton-wallet

bash ~/.openclaw/skills/exton-wallet/scripts/install.sh
```

Перезапустить OpenClaw или начать новую сессию.

## Подключение кошелька

В чате с OpenClaw скажи: **"Подключи мой Exton кошелёк"**

Агент попросит Recovery Code — получить в Exton Android App:
Settings → Exton MultiSig → Show Recovery Code.

## Что умеет

| Операция | Keystone нужен? |
|----------|----------------|
| Баланс, история, jettons | Нет |
| Резолв .ton доменов | Нет |
| Отправка через whitelist/лимиты | Нет (после настройки) |
| Произвольный перевод | Да (QR в чате) |
| Установка плагина | Да (однократно) |

## Как работает подпись

```
Ты: "Отправь 100 TON на wallet.ton"

Агент: [QR картинка] "Отсканируйте на Keystone 3 Pro"

Ты: [фото экрана Keystone с подписью]

Агент: "Отправлено 100 TON"
```

## Безопасность

- Приватный ключ Keystone никогда не покидает устройство
- On-chain плагины ограничивают автоматику (whitelist, лимиты)
- Мгновенный отзыв: удаление плагина одной подписью

## Требования

- Python 3.9+
- Keystone 3 Pro
- Exton Wallet Android App
- OpenClaw с Telegram/WhatsApp каналом
