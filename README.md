# Exton Wallet — OpenClaw Skill

Управляй криптокошельком Exton на TON через AI-агента. Приватный ключ никогда не покидает аппаратный кошелёк Keystone 3 Pro.

## Установка

```bash
# 1. Скопировать skill в OpenClaw
cp -r /path/to/exton/skill ~/.openclaw/skills/exton-wallet

# 2. Зависимости установятся автоматически при первом запуске
#    Или вручную:
bash ~/.openclaw/skills/exton-wallet/scripts/install.sh
```

## Подключение кошелька

В чате с OpenClaw:
```
"Подключи мой Exton кошелёк"
```

Агент попросит Recovery Code — его можно получить в Exton Android App:
Settings → Exton MultiSig → Recovery Code.

## Что умеет

**Без Keystone (автоматически):**
- Баланс, история, jettons
- Резолв .ton доменов
- Статус плагинов и лимитов
- Отправка через whitelist + daily-limit (после однократной настройки)

**С Keystone (QR в чате):**
- Любые переводы TON/jettons/NFT
- Установка и удаление плагинов
- Ротация ключей

## Как работает подпись

```
Ты: "Отправь 100 TON на wallet.ton"
     ↓
Агент: [QR картинка] "Отсканируйте на Keystone"
     ↓
Ты: [фото экрана Keystone с QR подписи]
     ↓
Агент: "✅ Отправлено 100 TON"
```

## Безопасность

- Приватный ключ Keystone **никогда** не покидает устройство
- On-chain плагины ограничивают автоматические операции (whitelist, лимиты)
- Даже при компрометации сервера — потери ограничены лимитами плагинов
- Мгновенный отзыв доступа: удаление плагина одной подписью Keystone

## Требования

- Python 3.9+
- Keystone 3 Pro (аппаратный кошелёк)
- Exton Wallet Android App (для создания MultiSig кошелька)
- OpenClaw с Telegram/WhatsApp каналом
