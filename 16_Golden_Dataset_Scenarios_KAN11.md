# 16. Golden Dataset: Матрица тестовых сценариев для KAN-11

## 1. Архитектурная концепция: Held-Out тестирование и защита от Data Leakage

В машинном обучении и оценке RAG-систем (LLM Evaluation) ключевым правилом является **разделение данных на обучающие/индексируемые и тестовые (Train/Test Split)**:

1. **Задачи `KAN-1` – `KAN-10`:** Составляют Базу Знаний (Knowledge Base) и уже векторизованы в PostgreSQL (`pgvector`). Тестировать систему на этих же задачах некорректно (Data Leakage / утечка данных), так как RAG будет тривиально находить «сам себя».
2. **Задача `KAN-11` (`WMS-1400`):** Специально создана как **Held-out задача** (отложенный тест, которого нет в базе знаний). Она проверяет способность RAG-системы обобщать опыт из смежных доменов (`KAN-7` трансферы, `KAN-3` мультисклад, `KAN-1` откат) и предлагать релевантные edge-кейсы для нового контекста.
3. **Тестируемая переменная:** Текст задачи `KAN-11` остается фиксированным, а варьируется **черновик тестировщика (`tester_draft`)**, моделируя различные уровни подготовки и поведения человека.

---

## 2. Сводная матрица сценариев Golden Dataset

| ID | Сценарий (`notes`) | `tester_draft` (Вход от тестировщика) | `expected_aspects` (Явные критерии для LLM-судьи) | Тип проверки / QA Метрика |
|:---:|---|---|---|---|
| **TC-01** | **Базовый тонкий ввод (Thin Draft)** | `Create a transfer to an open warehouse; Check the transfer appears in the destination inbound list` | `rollback / safe rollback on rejection; re-route / rerouting when warehouse closed; partial transfer logic; audit logging and trace` | **Completeness (Полнота):** RAG обязан найти все 4 ключевых edge-кейса, дополняя поверхностный позитивный черновик. |
| **TC-02** | **Человек уже учел Rollback (Deduplication 1)** | `Create a transfer to an open warehouse; Check the transfer appears in destination inbound list; Rollback if destination warehouse rejects transfer` | `re-route / rerouting when warehouse closed; partial transfer logic; audit logging and trace (MUST NOT contain rollback / duplicate rollback check)` | **Deduplication (Дедупликация):** RAG должен предложить недостающие пункты, но **НЕ дублировать** Rollback. |
| **TC-03** | **Человек уже учел Re-route (Deduplication 2)** | `Create a transfer to an open warehouse; Check the transfer appears in destination inbound list; Re-route to alternative warehouse if destination is closed` | `rollback / safe rollback on rejection; partial transfer logic; audit logging and trace (MUST NOT contain re-route / duplicate rerouting check)` | **Deduplication (Дедупликация):** RAG должен предложить недостающие пункты, но **НЕ дублировать** Re-route. |
| **TC-04** | **Идеальный сеньор-тестировщик (Full Coverage)** | `Create transfer; Check inbound list; Rollback on rejection without double-counting; Re-route if destination closed; Partial transfer logic; Audit log for routing decisions` | `MUST BE EMPTY (empty suggestions list / NOTHING TO ADD, no hallucinated checks)` | **Anti-Hallucination / Noise Gate:** RAG не должен спамить ненужными советами, если чек-лист уже полон. |
| **TC-05** | **Небрежный / разговорный ввод (Informal / Messy English)** | `1 make transfer to open wh; 2 check if in dest inbound list` | `rollback / safe rollback on rejection; re-route / rerouting when warehouse closed; partial transfer logic; audit logging and trace` | **Robustness (Устойчивость):** Способна ли система восстановить профессиональные чек-листы из небрежного сленгового черновика. |

---

## 3. Детальное описание каждого тест-кейса

### TC-01: Базовый тонкий ввод (Thin Draft)
* **Цель:** Проверить базовую способность RAG компенсировать недостаток опыта тестировщика.
* **Поведение:** Тестировщик указал только стандартный позитивный путь (создал $\rightarrow$ проверил).
* **Ожидание:** Система находит в базе знаний паттерны закрытия складов и откатов (`KAN-7`, `KAN-3`, `KAN-1`) и дополняет чек-лист 4 критическими edge-кейсами с колонкой `why`.

### TC-02: Дедупликация Rollback
* **Цель:** Проверить работу алгоритма исключения дубликатов (`_is_duplicate` + LLM prompt constraints).
* **Поведение:** Тестировщик уже сам догадался написать проверку на откат (`Rollback`).
* **Ожидание:** Система предлагает `Re-route`, `Partial transfer` и `Audit`, но в финальных предложениях **отсутствует** повторное предложение отката.

### TC-03: Дедупликация Re-route
* **Цель:** Проверить дедупликацию по альтернативному аспекту (маршрутизация).
* **Поведение:** Тестировщик уже написал проверку на перенаправление на резервный склад (`Re-route`).
* **Ожидание:** Система предлагает `Rollback`, `Partial transfer` и `Audit`, строго исключая повторы про `Re-route`.

### TC-04: Защита от спама и галлюцинаций (Full Coverage)
* **Цель:** Проверить поведение системы в ситуации, когда чек-лист уже идеален.
* **Поведение:** Введены все 6 обязательных проверок предметной области.
* **Ожидание:** Системный промпт выполняет условие *"If nothing relevant is missing, return an empty list"*. Ответ пустой (`[]`), в UI отображается `NOTHING TO ADD`.

### TC-05: Устойчивость к небрежному вводу (Informal / Messy English)
* **Цель:** Проверить робастность системы к разговорной речи, сокращениям (`wh` = warehouse) и отсутствию пунктуации.
* **Поведение:** Черновик написан в разговорном стиле со сленгом.
* **Ожидание:** Модель понимает суть, извлекает паттерны и формулирует строгие профессиональные проверки.

---

## 4. Представление в формате CSV (для `eval/datasets/golden_dataset.csv`)

```csv
task_id,domain,input_task,tester_draft,expected_aspects,notes
KAN-11,wms-transfer,"WMS-1400: Transfer stock to a destination warehouse that is mid-closure. When a destination warehouse is being decommissioned, incoming transfers must be handled safely (re-route, partial transfer, rollback).","Create a transfer to an open warehouse; Check the transfer appears in the destination inbound list","rollback / safe rollback on rejection; re-route / rerouting when warehouse closed; partial transfer logic; audit logging and trace","TC-01: Basic thin draft. RAG must suggest missing edge cases."
KAN-11,wms-transfer,"WMS-1400: Transfer stock to a destination warehouse that is mid-closure. When a destination warehouse is being decommissioned, incoming transfers must be handled safely (re-route, partial transfer, rollback).","Create a transfer to an open warehouse; Check the transfer appears in destination inbound list; Rollback if destination warehouse rejects transfer","re-route / rerouting when warehouse closed; partial transfer logic; audit logging and trace (MUST NOT contain rollback / duplicate rollback check)","TC-02: Deduplication. Tester already covered Rollback, RAG must not repeat it."
KAN-11,wms-transfer,"WMS-1400: Transfer stock to a destination warehouse that is mid-closure. When a destination warehouse is being decommissioned, incoming transfers must be handled safely (re-route, partial transfer, rollback).","Create a transfer to an open warehouse; Check the transfer appears in destination inbound list; Re-route to alternative warehouse if destination is closed","rollback / safe rollback on rejection; partial transfer logic; audit logging and trace (MUST NOT contain re-route / duplicate rerouting check)","TC-03: Deduplication. Tester already covered Re-route, RAG must not repeat it."
KAN-11,wms-transfer,"WMS-1400: Transfer stock to a destination warehouse that is mid-closure. When a destination warehouse is being decommissioned, incoming transfers must be handled safely (re-route, partial transfer, rollback).","Create transfer; Check inbound list; Rollback on rejection without double-counting; Re-route if destination closed; Partial transfer logic; Audit log for routing decisions","MUST BE EMPTY (empty suggestions list / NOTHING TO ADD, no hallucinated checks)","TC-04: Full coverage. RAG must return an empty list and avoid over-generation."
KAN-11,wms-transfer,"WMS-1400: Transfer stock to a destination warehouse that is mid-closure. When a destination warehouse is being decommissioned, incoming transfers must be handled safely (re-route, partial transfer, rollback).","1 make transfer to open wh; 2 check if in dest inbound list","rollback / safe rollback on rejection; re-route / rerouting when warehouse closed; partial transfer logic; audit logging and trace","TC-05: Informal / messy draft. Robustness check for colloquial and abbreviated human input."
```
