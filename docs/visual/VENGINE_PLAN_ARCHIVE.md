# Implementation Plan: GPU Post-Processing Shake & World-Pass Overlay

Перевод экранных эффектов vEngine на GPU Post-Processing Pipeline (`entity_outline`) и World-Pass Overlay для полной поддержки F1, независимости от GUI Scale (1/2/3/4) и кинематографичной шейдерной тряски.

---

## Technical Architecture

### 1. GPU Screen Shake (`entity_outline.json` Post-Shader Pipeline)
- **Принцип работы**: 
  - Сервер спавнит персональный `item_display` с тегом `glowing: true` на расстоянии 0.8 блока перед глазами игрока (в поле зрения камеры).
  - При обнаружении glowing-сущности Minecraft автоматически запускает GPU-конвейер постобработки `shaders/post/entity_outline.json`.
  - Шейдер `screen_shake.fsh` выполняет многочастотное гармоническое смещение UV-координат всего кадрового буфера (`minecraft:main`):
    `uv += vec2(sin(t * 1.7) * 0.0035 + sin(t * 3.1) * 0.002, cos(t * 2.3) * 0.0035 + cos(t * 4.2) * 0.002) * intensity;`
- **Преимущества**:
  - **100% видно в F1** (постобработка накладывается на сам мир).
  - **0% влияния GUI Scale** (работает в экранных пикселях GPU).
  - **Курсор/прицел неподвижен** (мышь игрока свободна, трясется сам экран на видеокарте).
  - **Без урона и красных вспышек**.

---

### 2. Fullscreen World-Pass Overlay (`rendertype_item_entity_translucent_cull.vsh`)
- **Принцип работы**:
  - Текстура оверлея (`heart_lvl1`, `heart_lvl2`, `heart_lvl3`) отображается через Display-носитель в мировом проходе рендера.
  - Вершинный шейдер `rendertype_item_entity_translucent_cull.vsh` перехватывает квад носителя и проецирует вершины напрямую в NDC-пространство экрана `[-1.0, 1.0]`.
- **Преимущества**:
  - **100% видно в F1** (мировой рендер не скрывается кнопкой F1).
  - **100% одинаковый размер на GUI Scale 1, 2, 3, 4 и Auto**.
  - **Идеальное заполнение в оконном режиме любого размера**.

---

## Proposed Changes

### Resource Pack (`temp/vEngine_ResourcePack_1.21.11` + ItemsAdder)

#### [MODIFY] `assets/minecraft/shaders/post/entity_outline.json`
- Конфигурация 2-проходного пост-конвейера (screen_shake -> blit) с передачей GameTime и OutSize.

#### [MODIFY] `assets/minecraft/shaders/program/screen_shake.fsh`
- Высокочастотный GLSL шейдер вибрации кадрового буфера.

#### [MODIFY] `assets/minecraft/shaders/core/rendertype_item_entity_translucent_cull.vsh`
- Вершинный хук проекции в NDC-пространство `[-1.0, 1.0]`.

---

### Denizen Scripts

#### [MODIFY] [`complex/libs/vEngine/effects.dsc`](file:///c:/Users/Admin/Desktop/Denizen/result/complex/libs/vEngine/effects.dsc)
- Управление жизненным циклом персонального Display Carrier перед взглядом игрока.
- Автоматическая очистка при выходе, смерти и перезагрузке скриптов.
- Двойной конвейер: Post-Shader GPU тряска + оверлей.

---

## Verification Plan

### Automated Verification
- `dcore_rp_lint.py` — проверка корректности post JSON, core JSON и GLSL 150/330.
- `dcore_lint.py` — проверка жизненного цикла носителей и отсутствия утечек сущностей.

### Manual Verification
- Проверка в игре с F1 (оверлей и тряска остаются активны).
- Проверка при переключении GUI Scale (1, 2, 3, 4) — размер стабилен.
- Проверка в оконном режиме при ресайзе окна.
