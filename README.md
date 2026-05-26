# Battery Cards

**Battery Cards** — custom integration для Home Assistant, которая создаёт унифицированные батарейные сенсоры вида:

```text
sensor.<object_id>_battery_card
```

Battery Cards — это не замена существующим батарейным инструментам, а связующий слой поверх двух отличных компонентов Home Assistant:

- [Battery Notes for Home Assistant](https://github.com/andrew-codechimp/ha-battery-notes/) — используется как сервисная книжка батареек: тип, количество, дата замены и кнопка “батарейка заменена”.
- [Battery State Card](https://github.com/maxwroc/battery-state-card) — используется как визуальный слой для отображения батареек на dashboard.

Battery Cards находится между реальными/виртуальными источниками батареи и этими компонентами. Интеграция превращает обычные, нестандартные или вообще “кривые” источники состояния в нормальный battery sensor с `device_class: battery`.

Идея простая:

```text
Любой реальный / виртуальный / странный источник батарейки
        ↓
Battery Cards
        ↓
sensor.<object_id>_battery_card
        ↓
Battery Notes       → тип, количество, дата замены
Battery State Card  → красивая отрисовка на dashboard
```

То есть Battery Cards — это адаптер и нормализатор батарейных данных, а не просто ещё одна карточка или отдельный sensor.

---

## Зачем это нужно

В Home Assistant батарейные устройства ведут себя по-разному.

Одни устройства честно отдают процент батареи:

```text
sensor.motion_battery = 87
```

Другие вообще не имеют battery entity, но батарейки там есть и их надо менять.

Например:

- RF433 / Nobito датчики температуры могут не иметь battery sensor;
- HomGar / RainPoint могут быть облачными и косвенно показывать состояние через доступность;
- некоторые Zigbee / Tuya устройства могут отдавать только `battery_low`;
- некоторые устройства отдают только voltage в `mV` или `V`;
- некоторые устройства имеют нормальный battery sensor, но хочется привести их к единому формату для Battery Notes и dashboard.

Без Battery Cards приходится делать отдельный YAML/template sensor для каждого нестандартного устройства.

Battery Cards решает это через GUI и создаёт нормальный battery sensor для любого такого случая.

---

## Архитектура

```text
Любое устройство / source entity
        ↓
Battery Cards
        ↓
sensor.xxx_battery_card
        ↓
Battery Notes
        ↓
battery-state-card
        ↓
dashboard / NOC / ha_battery_overall
```

Каждый слой делает свою работу:

| Слой | Задача |
|---|---|
| Source entity | Реальный источник данных: процент, температура, доступность, battery_low, voltage |
| Battery Cards | Нормализация в единый battery sensor |
| Battery Notes | Метаданные батарейки: тип, количество, дата замены, кнопка замены |
| Battery State Card | Отрисовка батареек на dashboard |
| ha_battery_overall / NOC | Общий статус и подсчёт проблемных батареек |

---

## Что создаёт интеграция

Для каждой записи Battery Cards создаёт один sensor:

```text
sensor.<object_id>_battery_card
```

Например:

```text
Object ID: emastiff
```

создаст:

```text
sensor.emastiff_battery_card
```

Этот sensor имеет:

```yaml
device_class: battery
state_class: measurement
unit_of_measurement: "%"
```

и может использоваться как обычный батарейный сенсор.

---

## Основные возможности v0.2.0

Battery Cards поддерживает два основных режима:

```text
Physical
Virtual
```

### Physical

Для устройств, которые уже отдают реальный процент батареи.

```text
source = 87 → battery_card = 87%
```

### Virtual

Для устройств, которые не отдают процент батареи напрямую.

Battery Cards вычисляет итоговый заряд по выбранному правилу:

```text
source_unavailable
temperature_zero
battery_low_binary
voltage_threshold
```

---

# Режим Physical

## Описание

`Physical` используется для устройств, которые уже отдают реальный процент батареи.

Пример:

```text
sensor.aqara_cube_battery = 100
sensor.leak_sensor_battery = 87
sensor.temperature_sensor_battery = 59
```

Battery Cards просто копирует значение и нормализует его в:

```text
sensor.xxx_battery_card
```

## Логика

```text
source = 59          → 59%
source = 87          → 87%
source = 100         → 100%
source unavailable   → 0%
source unknown       → 0%
source missing       → 0%
source not numeric   → 0%
```

`0%` выбран специально, чтобы dashboard и NOC не ломались на `unknown`, а сразу показывали проблему красным.

## Когда выбирать Physical

Выбирай Physical, если у устройства уже есть sensor, который отдаёт процент батареи:

```text
sensor.xxx_battery
```

---

# Режим Virtual

## Описание

`Virtual` используется для устройств, которые не отдают процент батареи напрямую.

Battery Cards вычисляет батарейку по выбранному правилу и выдаёт итоговый процент:

```text
0%
10%
100%
```

---

# Virtual Rules

## 1. Source unavailable → 0%

GUI label:

```text
Доступно = 100%, недоступно = 0%
```

## Логика

```text
source доступен       → 100%
source unavailable    → 0%
source unknown        → 0%
source missing        → 0%
```

## Для чего

Для устройств, где факт доступности уже является главным признаком жизни.

Например:

- HomGar;
- RainPoint;
- облачные датчики;
- устройства, которые просто становятся unavailable при проблеме.

## Пример

```text
source_entity: sensor.homgar_temperature
rule: source_unavailable
```

Если sensor доступен — Battery Cards покажет:

```text
100%
```

Если sensor пропал — Battery Cards покажет:

```text
0%
```

---

## 2. Temperature 0°C / unavailable → 0%

GUI label:

```text
0°C или недоступно = 0%, иначе = 100%
```

## Логика

```text
temperature нормальная      → 100%
temperature = 0°C           → 0%
source unavailable          → 0%
source unknown              → 0%
source missing              → 0%
source not numeric          → 0%
```

## Для чего

Для устройств, которые при смерти батарейки или отвале начинают отдавать `0°C`.

Например:

- Nobito RF433;
- похожие RF/433 датчики;
- любые датчики, у которых `0°C` является явным признаком проблемы.

## Пример

```text
source_entity: sensor.nobito_rf433_2c018_temperature
rule: temperature_zero
```

Если Nobito показывает:

```text
23.5°C → 100%
0°C    → 0%
unavailable → 0%
```

---

## 3. Battery Low Binary → 10%

GUI label:

```text
Battery Low: low/on = 10%, normal/off = 100%, недоступно = 0%
```

## Логика

```text
on / true / low / problem / 1        → 10%
off / false / normal / clear / 0     → 100%
unknown / unavailable / missing      → 0%
другое числовое значение             → 0%
```

## Для чего

Для устройств, которые не отдают процент батареи, но имеют только флаг низкой батареи:

```text
binary_sensor.xxx_battery_low
```

или sensor со значением:

```text
low / normal
true / false
on / off
1 / 0
```

## Почему low = 10%, а не 0%

`battery_low` обычно означает не “датчик уже умер”, а “пора менять батарейку”.

Поэтому Battery Cards отдаёт `10%`, чтобы карточка и NOC показали критическое состояние, но логически это не полный ноль.

## Пример

```text
source_entity: binary_sensor.some_sensor_battery_low
rule: battery_low_binary
```

Если:

```text
binary_sensor.some_sensor_battery_low = off
```

Battery Cards покажет:

```text
100%
```

Если:

```text
binary_sensor.some_sensor_battery_low = on
```

Battery Cards покажет:

```text
10%
```

---

## 4. Voltage Threshold → 10%

GUI label:

```text
Напряжение: ниже minV = 10%, выше = 100%, недоступно = 0%
```

## Логика

```text
voltage < minV                 → 10%
voltage >= minV                → 100%
source unavailable             → 0%
source unknown                 → 0%
source missing                 → 0%
source not numeric             → 0%
```

## Для чего

Для устройств, которые не отдают процент батареи, но отдают напряжение:

```text
sensor.xxx_voltage = 2950 mV
sensor.xxx_voltage = 2.95 V
```

Battery Cards умеет понимать:

```text
2.95 V
2950 mV
2950
2,95
```

## Определение единиц

Battery Cards пытается определить единицы автоматически:

```text
unit_of_measurement = mV     → делит на 1000
unit_of_measurement = V      → оставляет как есть
state содержит "mV"          → делит на 1000
state содержит "V"           → оставляет как есть
число > 20                   → считает как mV auto
число <= 20                  → считает как V auto
```

Примеры:

```text
2950 mV → 2.95 V
2.95 V  → 2.95 V
2950    → 2.95 V
3.0     → 3.0 V
```

## Диагностические атрибуты voltage

Для voltage rule Battery Cards добавляет атрибуты:

```yaml
voltage: 2.95
voltage_raw: "2950"
voltage_unit: "mV"
voltage_unit_detected: "mV_auto"
min_voltage: 2.7
battery_type_hint: "cr_3v_coin"
```

Это помогает понять, как именно Battery Cards распарсил напряжение.

## Важно

`voltage`, `voltage_raw`, `voltage_unit` и `voltage_unit_detected` заполняются только для правила:

```text
voltage_threshold
```

Для остальных правил будет:

```yaml
voltage: null
voltage_raw: null
voltage_unit: null
voltage_unit_detected: not_applicable
```

Это сделано специально, чтобы температура или процент батареи не отображались как “напряжение”.

---

# Подсказки minV

Для `voltage_threshold` в GUI есть подсказки по типу батареи.

Это не жёсткая истина, а стартовая точка.

Реальный порог зависит от:

- химии батарейки;
- конкретного устройства;
- качества батарейки;
- температуры;
- того, при каком напряжении устройство реально начинает глючить.

## Примерные стартовые значения

| Тип батареи | Стартовый minV |
|---|---:|
| CR2032 / CR2450 / 3V coin | 2.7 V |
| 1× AA / AAA alkaline | 1.1 V |
| 2× AA / AAA alkaline | 2.2 V |
| 1× AA / AAA NiMH | 1.0 V |
| 2× AA / AAA NiMH | 2.0 V |
| Custom | вручную |

---

# Battery Notes integration

Battery Cards хорошо работает вместе с Battery Notes.

Battery Cards создаёт основную сущность:

```text
sensor.xxx_battery_card
```

После этого эту сущность можно добавить в Battery Notes.

Battery Notes создаёт связанные сущности:

```text
sensor.xxx_battery_card_battery_type
sensor.xxx_battery_card_battery_last_replaced
button.xxx_battery_card_battery_replaced
```

Battery Cards автоматически читает эти sibling-сущности и добавляет их данные в атрибуты основного battery sensor.

---

## Атрибуты Battery Notes

Battery Cards подтягивает:

```yaml
battery_type_and_quantity: "2× AAA"
battery_last_replaced: "22.05.26"
battery_type_entity: "sensor.xxx_battery_card_battery_type"
battery_last_replaced_entity: "sensor.xxx_battery_card_battery_last_replaced"
battery_replaced_button: "button.xxx_battery_card_battery_replaced"
```

Это позволяет красиво выводить данные в `battery-state-card`.

---

# Location / Area / Floor

Battery Cards подтягивает помещение и локацию из Home Assistant.

Основная логика:

1. сначала смотрит area/floor у самой сущности Battery Cards;
2. если там ничего нет — смотрит source entity;
3. если ничего не найдено — показывает `—`.

## Атрибуты location

```yaml
source_area: "Туалет"
source_floor: "Дом"
source_location: "Дом"
source_location_icon: "🏢"
source_location_display: "🏢 Дом"
source_location_resolved_from: "battery_card_entity"
```

## Иконки location

Battery Cards определяет иконку по имени floor/location.

Для дома:

```text
дом
home
apartment
flat
квартира
```

иконка:

```text
🏢
```

Для дачи:

```text
дача
chalet
cottage
country
загород
```

иконка:

```text
🏠
```

---

# Атрибуты Battery Cards sensor

Пример атрибутов physical sensor:

```yaml
state_class: measurement
battery_card: true
battery_mode: physical
battery_rule: physical_percent
battery_reason: source_percent
source_entity: sensor.emastiff_battery
source_state: "87"
source_area: Туалет
source_floor: Дом
source_location: Дом
source_location_icon: 🏢
source_location_display: 🏢 Дом
source_location_resolved_from: battery_card_entity
raw_source_area: Туалет
raw_source_floor: Дом
raw_source_location: Дом
source_friendly_name: eMastiff Батарея
battery_type_entity: sensor.emastiff_battery_card_battery_type
battery_last_replaced_entity: sensor.emastiff_battery_card_battery_last_replaced
battery_replaced_button: button.emastiff_battery_card_battery_replaced
battery_type_and_quantity: CR2032
battery_last_replaced: 22.05.26
voltage: null
voltage_raw: null
voltage_unit: null
voltage_unit_detected: not_applicable
min_voltage: 2.7
battery_type_hint: custom
unit_of_measurement: "%"
device_class: battery
friendly_name: Датчик протечки
```

---

# battery_reason

`battery_reason` показывает, почему Battery Cards выставил текущее значение.

## Общие причины

| battery_reason | Значение |
|---|---|
| `source_missing` | source entity не найден |
| `source_unavailable` | source entity unavailable/unknown |
| `source_not_numeric` | ожидалось число, но пришёл текст |
| `ok` | всё нормально |
| `unknown_rule` | неизвестное правило |

## Physical

| battery_reason | Значение |
|---|---|
| `source_percent` | успешно прочитан процент батареи |
| `source_not_numeric` | source не является числом |
| `source_unavailable` | source недоступен |

## Temperature Zero

| battery_reason | Значение |
|---|---|
| `temperature_zero` | температура равна 0°C |
| `ok` | температура нормальная |
| `source_not_numeric` | температура не число |

## Battery Low Binary

| battery_reason | Значение |
|---|---|
| `low_binary_on` | low battery активен |
| `low_binary_off` | low battery не активен |
| `low_binary_invalid_numeric` | выбран неправильный числовой sensor, например 87 |
| `low_binary_unknown_value` | неизвестное текстовое состояние |

## Voltage Threshold

| battery_reason | Значение |
|---|---|
| `voltage_below_threshold` | напряжение ниже minV |
| `voltage_ok` | напряжение выше или равно minV |
| `voltage_not_numeric` | напряжение не удалось распарсить |

---

# Установка

Скопировать папку интеграции:

```text
/config/custom_components/battery_cards/
```

или:

```text
/homeassistant/custom_components/battery_cards/
```

Внутри должны быть файлы:

```text
__init__.py
manifest.json
const.py
config_flow.py
sensor.py
services.yaml
strings.json
README.md
```

После копирования выполнить полный restart Home Assistant:

```text
Settings → System → Restart Home Assistant
```

---

# Структура архива / проекта

Рекомендуемая структура:

```text
custom_components/
  battery_cards/
    __init__.py
    manifest.json
    const.py
    config_flow.py
    sensor.py
    services.yaml
    strings.json
    README.md
    brand/
      icon.png

dashboard/
  overall.yaml
  physical.yaml
  virtual.yaml

packages/
  ha_batteries.yaml

README.md
```

## Что где лежит

| Файл / папка | Назначение |
|---|---|
| `custom_components/battery_cards/` | сама интеграция |
| `packages/ha_batteries.yaml` | package с агрегирующим sensor по всем Battery Cards |
| `dashboard/overall.yaml` | общая кнопка/карточка состояния батареек |
| `dashboard/physical.yaml` | пример dashboard-блока для физических батареек |
| `dashboard/virtual.yaml` | пример dashboard-блока для виртуальных батареек |
| `brand/icon.png` | иконка интеграции |

---

# Добавление Battery Card через GUI

Открыть:

```text
Settings → Devices & services → Add integration → Battery Cards
```

---

## Шаг 1. Основные параметры

### Friendly name

Человеческое имя батарейки.

Пример:

```text
Датчик протечки
```

### Object ID

Технический идентификатор.

Пример:

```text
emastiff
```

Из него будет создана сущность:

```text
sensor.emastiff_battery_card
```

Object ID лучше задавать сразу правильно, потому что он связан с Battery Notes naming convention.

### Battery type

Выбор режима:

```text
Обычная батарейка — источник уже отдаёт %
```

или:

```text
Вычисляемая батарейка — процента нет, считаем по признаку
```

---

# Рекомендованный workflow добавления новой батарейки

## Обычная физическая батарейка

1. Battery Cards → Add entry.
2. Mode: Physical.
3. Source entity: реальный battery sensor.
4. Создался `sensor.xxx_battery_card`.
5. Назначить area/floor самой сущности `sensor.xxx_battery_card`, если нужно красиво видеть Дом/Дача/комнату.
6. Battery Notes → добавить `sensor.xxx_battery_card`.
7. Указать тип батарейки, количество, дату замены.
8. Dashboard → добавить `sensor.xxx_battery_card` в `physical.yaml` / свой dashboard-блок.

---

## Виртуальная батарейка

1. Battery Cards → Add entry.
2. Mode: Virtual.
3. Выбрать правило.
4. Выбрать source entity.
5. Создался `sensor.xxx_battery_card`.
6. Назначить area/floor самой сущности `sensor.xxx_battery_card`, если нужно красиво видеть Дом/Дача/комнату.
7. Battery Notes → добавить `sensor.xxx_battery_card`.
8. Указать тип батарейки, количество, дату замены.
9. Dashboard → добавить `sensor.xxx_battery_card` в `virtual.yaml` / свой dashboard-блок.

---

# Примеры настройки

## Пример 1. Обычный физический battery sensor

Устройство уже отдаёт:

```text
sensor.emastiff_battery = 87
```

Battery Cards:

```text
Friendly name: Датчик протечки
Object ID: emastiff
Mode: Physical
Source entity: sensor.emastiff_battery
```

Итог:

```text
sensor.emastiff_battery_card = 87%
```

---

## Пример 2. Nobito через temperature_zero

Nobito не отдаёт батарейку, но при смерти показывает `0°C`.

Battery Cards:

```text
Friendly name: Спальня
Object ID: nobito_spalnya
Mode: Virtual
Rule: 0°C или недоступно = 0%, иначе = 100%
Source entity: sensor.nobito_rf433_2c018_temperature
```

Итог:

```text
температура 23.5°C → sensor.nobito_spalnya_battery_card = 100%
температура 0°C    → sensor.nobito_spalnya_battery_card = 0%
unavailable        → sensor.nobito_spalnya_battery_card = 0%
```

---

## Пример 3. HomGar через source_unavailable

Battery Cards:

```text
Friendly name: Улица
Object ID: homgar_ulica
Mode: Virtual
Rule: Доступно = 100%, недоступно = 0%
Source entity: sensor.homgar_ulica_temperature
```

Итог:

```text
source доступен    → 100%
source unavailable → 0%
```

---

## Пример 4. Устройство с battery_low

Battery Cards:

```text
Friendly name: Датчик движения
Object ID: motion_low
Mode: Virtual
Rule: Battery Low: low/on = 10%, normal/off = 100%, недоступно = 0%
Source entity: binary_sensor.motion_battery_low
```

Итог:

```text
battery_low = off → 100%
battery_low = on  → 10%
unavailable       → 0%
```

---

## Пример 5. Устройство с voltage

Battery Cards:

```text
Friendly name: Датчик окна
Object ID: window_voltage
Mode: Virtual
Rule: Напряжение ниже minV = 10%
Source entity: sensor.window_battery_voltage
Battery type hint: CR2032 / CR2450 / 3V coin
minV: 2.7
```

Итог:

```text
3.0 V   → 100%
2.95 V  → 100%
2.65 V  → 10%
unknown → 0%
```

---

# Добавление в Battery Notes

После создания `sensor.xxx_battery_card` нужно добавить его в Battery Notes.

Пример:

```text
Battery Notes → Add device/entity
Entity: sensor.emastiff_battery_card
Battery type: CR2032
Battery quantity: 1
Last replaced: 22.05.26
```

Battery Notes создаст:

```text
sensor.emastiff_battery_card_battery_type
sensor.emastiff_battery_card_battery_last_replaced
button.emastiff_battery_card_battery_replaced
```

Battery Cards автоматически подтянет эти данные в атрибуты.

---

# Dashboard

В комплекте могут быть три dashboard-примера:

```text
dashboard/overall.yaml
dashboard/physical.yaml
dashboard/virtual.yaml
```

Они не обязательны для работы интеграции, но показывают рекомендуемую схему отображения.

---

## `dashboard/overall.yaml`

Общая карточка/кнопка состояния батареек.

Использует агрегирующий sensor из package:

```text
sensor.ha_battery_overall
```

Идея:

```text
зелёный  → всё нормально
жёлтый   → есть предупреждения
красный  → есть критичные батарейки
```

Обычно эту карточку удобно добавить на NOC / главную страницу.

---

## `dashboard/physical.yaml`

Dashboard-блок для физических батареек.

Использует:

```text
custom:battery-state-card
```

Рекомендуемый формат второй строки:

```yaml
secondary_info: |
  {attributes.source_location_display} · 📍 {attributes.source_area}
  🔋 {attributes.battery_type_and_quantity} · 🗓 {attributes.battery_last_replaced}
```

То есть на dashboard видно:

```text
Датчик протечки
🏢 Дом · 📍 Туалет
🔋 CR2032 · 🗓 22.05.26
```

---

## `dashboard/virtual.yaml`

Dashboard-блок для виртуальных батареек.

Использует тот же принцип, что `physical.yaml`.

Виртуальные батарейки выглядят на dashboard так же, как физические:

```text
sensor.nobito_zal_battery_card
sensor.homgar_ulica_battery_card
sensor.nobito_spalnya_battery_card
```

Это главная идея Battery Cards: dashboard не должен знать, настоящая это батарейка, виртуальная или вычисляемая.

---

## Пример минимального `battery-state-card`

```yaml
type: custom:battery-state-card
filter: {}
secondary_info: |
  {attributes.source_location_display} · 📍 {attributes.source_area}
  🔋 {attributes.battery_type_and_quantity} · 🗓 {attributes.battery_last_replaced}
round: 0
entities:
  - entity: sensor.emastiff_battery_card
    name: "Датчик протечки"
    tap_action:
      action: more-info
      entity: button.emastiff_battery_card_battery_replaced
sort:
  by: state
colors:
  steps:
    - value: 20
      color: red
    - value: 30
      color: orange
    - value: 100
      color: green
```

---

## Пример CSS для `battery-state-card`

Этот стиль делает название жирным, а дополнительную информацию обычным шрифтом и в две строки:

```yaml
style: |
  .name {
    font-weight: 700 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }

  .secondary,
  .secondary-info,
  .battery-secondary,
  .entity-secondary,
  .text-secondary,
  .info,
  .name .secondary,
  .name .secondary-info,
  .name .battery-secondary,
  .name .entity-secondary,
  .name .text-secondary,
  .name .info {
    font-weight: 400 !important;
    white-space: pre-line !important;
    overflow: visible !important;
    text-overflow: unset !important;
    line-height: 1.22em !important;
    max-height: none !important;
  }

  .entity-row,
  .battery-row,
  .row {
    min-height: 60px !important;
    height: auto !important;
    align-items: center !important;
  }
```

---

## Пример popup по тапу

Можно сделать tap action, который открывает popup с тремя сущностями:

- дата замены;
- кнопка замены;
- итоговая батарейка.

```yaml
- entity: sensor.emastiff_battery_card
  name: "Датчик протечки"
  tap_action:
    action: fire-dom-event
    browser_mod:
      service: browser_mod.popup
      data:
        browser_id: THIS
        title: Датчик протечки — батарейка
        size: normal
        content:
          type: vertical-stack
          cards:
            - type: custom:button-card
              entity: sensor.emastiff_battery_card_battery_last_replaced
              name: Дата замены батарейки
              icon: mdi:calendar-refresh
              show_state: true
              tap_action:
                action: more-info

            - type: custom:button-card
              entity: button.emastiff_battery_card_battery_replaced
              name: Отметить замену батарейки
              icon: mdi:battery-sync
              show_state: false
              tap_action:
                action: more-info

            - type: custom:button-card
              entity: sensor.emastiff_battery_card
              name: Итоговая батарейка
              icon: mdi:battery-heart-variant
              show_state: true
              tap_action:
                action: more-info
```

---

# Package `ha_batteries.yaml`

Файл:

```text
packages/ha_batteries.yaml
```

может содержать агрегирующий sensor, который автоматически собирает все Battery Cards.

Главный маркер:

```yaml
battery_card: true
```

Каждый Battery Cards sensor имеет этот атрибут.

Важно фильтровать именно основные сущности:

```jinja
s.entity_id.endswith('_battery_card') and s.attributes.get('battery_card') == true
```

Это нужно, чтобы не считать sibling-сущности Battery Notes:

```text
sensor.xxx_battery_card_battery_type
sensor.xxx_battery_card_battery_last_replaced
```

---

## Пример логики агрегатора

```jinja
{% set cards = states.sensor
  | selectattr('entity_id', 'search', '_battery_card$')
  | selectattr('attributes.battery_card', 'eq', true)
  | list
%}
```

---

## Что обычно считает `ha_battery_overall`

Агрегатор может считать:

```text
total      → всего Battery Cards
ok         → нормальные
warning    → низкий заряд / предупреждение
critical   → критичные
problem    → проблемные
min_level  → минимальный заряд
summary    → короткая строка для dashboard
problems   → список проблемных батареек
```

Рекомендуемая логика:

```text
0–20%   → critical
21–30%  → warning
31–100% → ok
```

Точные пороги можно менять под свою систему.

---

# Service

Интеграция добавляет service:

```text
battery_cards.reload
```

Он перезагружает все Battery Cards entries.

```yaml
service: battery_cards.reload
```

Обычно после обновления файлов всё равно лучше делать полный restart Home Assistant.

---

# Обновление интеграции

1. Заменить файлы в:

```text
/config/custom_components/battery_cards/
```

2. Выполнить полный restart Home Assistant.

3. Проверить:

```text
Settings → Devices & services → Battery Cards
```

4. Проверить одну сущность:

```text
sensor.xxx_battery_card
```

В атрибутах должны быть:

```yaml
battery_card: true
battery_mode: ...
battery_rule: ...
battery_reason: ...
```

---

# Совместимость v0.1.0 → v0.2.0

Старые записи Battery Cards сохраняются.

Для старых Physical записей, где раньше мог быть rule `source_unavailable`, новая версия всё равно использует внутреннее правило:

```text
physical_percent
```

Для старых Virtual записей правила остаются прежними:

```text
source_unavailable
temperature_zero
```

Новые поля:

```text
min_voltage
battery_type_hint
```

имеют fallback значения и не ломают старые записи.

Пример старой virtual-сущности после обновления:

```yaml
battery_mode: virtual
battery_rule: source_unavailable
battery_reason: ok
source_entity: sensor.homgar_ulica_temperature
source_state: "29.1"
voltage: null
voltage_raw: null
voltage_unit: null
voltage_unit_detected: not_applicable
```

---

# Troubleshooting

## Интеграция не стартует

Смотреть логи:

```text
Settings → System → Logs
```

Искать:

```text
battery_cards
```

Типичные проблемы:

- синтаксическая ошибка в `config_flow.py`;
- не все файлы скопированы;
- папка лежит не там;
- Home Assistant не был полностью перезапущен;
- старый `.pyc` / кэш после неполной замены файлов.

Правильный путь:

```text
/config/custom_components/battery_cards/
```

Неправильно:

```text
/config/custom_components/config_flow.py
/config/custom_components/sensor.py
/config/custom_components/manifest.json
```

---

## Sensor показывает 0%

Проверить атрибут:

```yaml
battery_reason
```

Возможные причины:

```text
source_missing
source_unavailable
source_not_numeric
temperature_zero
low_binary_on
low_binary_invalid_numeric
voltage_below_threshold
voltage_not_numeric
```

---

## Battery Notes данные не подтянулись

Проверить, что в Battery Notes добавлен именно:

```text
sensor.xxx_battery_card
```

а не исходный sensor.

Проверить, что существуют sibling-сущности:

```text
sensor.xxx_battery_card_battery_type
sensor.xxx_battery_card_battery_last_replaced
button.xxx_battery_card_battery_replaced
```

---

## На dashboard вместо Дом/Дача стоит прочерк

Проверить area/floor у самой сущности Battery Cards.

Лучший вариант:

```text
sensor.xxx_battery_card → assign area/floor в Home Assistant UI
```

Если у самой Battery Cards сущности area не задана, интеграция попробует взять area/floor у source entity.

---

## Voltage показывает странное значение

Проверить атрибуты:

```yaml
voltage
voltage_raw
voltage_unit
voltage_unit_detected
min_voltage
```

Если source отдаёт `295` без единиц, Battery Cards может считать это как `mV_auto`.

Для таких нестандартных устройств может понадобиться ручная корректировка логики в будущей версии.

---

## В атрибутах voltage = null

Это нормально для всех правил, кроме:

```text
voltage_threshold
```

Для `physical_percent`, `source_unavailable`, `temperature_zero`, `battery_low_binary` будет:

```yaml
voltage: null
voltage_raw: null
voltage_unit: null
voltage_unit_detected: not_applicable
```

---

# Design principles

Battery Cards не пытается заменить Battery Notes или battery-state-card.

Она делает только одну работу:

```text
любой странный батарейный источник → нормальный battery sensor
```

Battery Notes отвечает за сервисную информацию:

```text
тип батарейки
количество
дата замены
кнопка “заменено”
```

Battery State Card отвечает за визуализацию.

Dashboard/NOC отвечает за отображение статуса.

Так каждый слой делает своё дело.

---

# Roadmap

Возможные будущие улучшения:

- auto-discovery кандидатов `battery_low`;
- auto-discovery voltage sensors;
- отдельный выбор voltage unit: Auto / V / mV / cV;
- отдельная diagnostics page;
- экспорт списка всех Battery Cards;
- HACS packaging;
- README screenshots;
- GitHub repository;
- полноценная локализация RU/EN.

---

# Changelog

## v0.2.0

- Добавлены новые virtual rules:
  - `battery_low_binary`
  - `voltage_threshold`
- Добавлен многошаговый Config Flow.
- Physical mode больше не показывает лишний rule в GUI.
- Добавлены подсказки `min_voltage`.
- Добавлены voltage diagnostics:
  - `voltage`
  - `voltage_raw`
  - `voltage_unit`
  - `voltage_unit_detected`
- Voltage diagnostics теперь применяются только для `voltage_threshold`.
- Для остальных правил:
  - `voltage: null`
  - `voltage_raw: null`
  - `voltage_unit: null`
  - `voltage_unit_detected: not_applicable`
- Physical unavailable теперь показывает `0%`.
- Улучшен парсинг чисел:
  - `75%`
  - `75 %`
  - `75,5`
  - `2.95 V`
  - `2950 mV`
- Улучшены `battery_reason`.
- Улучшена совместимость со старыми entries.
- Добавлены dashboard-примеры:
  - `overall.yaml`
  - `physical.yaml`
  - `virtual.yaml`
- Добавлен package-пример:
  - `ha_batteries.yaml`

## v0.1.0

- Первый рабочий релиз.
- Physical mode.
- Virtual source_unavailable.
- Virtual temperature_zero.
- Интеграция с Battery Notes naming convention.
- Атрибут `battery_card: true`.
- Location/area/floor attributes.

---

# Credits

Battery Cards uses and complements these Home Assistant projects:

- [Battery Notes for Home Assistant](https://github.com/andrew-codechimp/ha-battery-notes/)
- [Battery State Card](https://github.com/maxwroc/battery-state-card)

Battery Cards for Home Assistant was generated with assistance of ChatGPT, but architecture, testing, and integration were done by the user.