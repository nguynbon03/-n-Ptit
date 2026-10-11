# SQLArena / Learn SQL / AI Pipeline Review Notes

## 1. Mục đích file này

File này là bản handoff tổng hợp để một agent khác đọc vào và nắm nhanh:

- Nguồn gốc hệ thống
- Scope thật của sản phẩm trong tài liệu
- Scope thật của repo hiện tại
- Kiến trúc tổng thể
- Pipeline AI sinh câu hỏi
- Thuật ngữ kỹ thuật quan trọng
- Khoảng cách giữa vision và implementation
- Những điểm cần review tiếp nếu phát triển tiếp

Mục tiêu là giảm thời gian onboarding và tránh nhầm lẫn giữa:

1. Đồ án Learn SQL đã triển khai thực tế
2. Tài liệu vision sản phẩm SQLArena
3. Pipeline AI Question Generator
4. Repo Python hiện tại

---

## 2. Nguồn đã đọc

### 2.1. Tài liệu ngoài repo

- `/Users/nguynbon03/Downloads/D20 - HỆ THỐNG ĐÁNH GIÁ TỰ ĐỘNG.pdf`
- `/Users/nguynbon03/Downloads/SQLArena.docx`
- `/Users/nguynbon03/Downloads/pipeline.html`

### 2.2. Repo hiện tại

- `README.md`
- `main.py`
- `pipeline.py`
- `llm_gateway.py`
- `schema.json`
- `docker-compose.yml`
- `Dockerfile`
- `requirements.txt`
- `Output/2026-04-26/sql_questions_easy_medium_hard_155056.json`

---

## 3. Kết luận ngắn gọn nhất

Nếu phải tóm tắt trong 5 dòng:

- `PDF` mô tả hệ thống gốc `Learn SQL`: hệ thống chấm SQL tự động theo kiến trúc microservice, đã chạy thực tế tại PTIT.
- `DOCX` mô tả `SQLArena`: bản mở rộng rất lớn từ Learn SQL thành một platform học SQL/NoSQL, có AI, gamification, SaaS multi-tenant, API doanh nghiệp.
- `pipeline.html` mô tả riêng một subsystem: `AI Question Generator Pipeline` 7 bước.
- Repo hiện tại `sqlarena-ai` chỉ là một prototype Python rất nhỏ cho việc sinh câu hỏi SQL bằng LLM + validate cú pháp SQL.
- Repo hiện tại chưa đại diện cho toàn bộ SQLArena trong DOCX; nó chỉ gần với phần nhỏ “AI sinh câu hỏi” và còn đơn giản hơn cả pipeline trong `pipeline.html`.

---

## 4. Bức tranh lớn: hệ thống này thực chất là gì?

### 4.1. Learn SQL trong PDF

Đây là hệ thống nền móng, đã được triển khai thực tế.

Vai trò:

- Cho sinh viên làm bài SQL
- Chạy SQL thật trên môi trường sandbox
- Chấm đúng/sai tự động
- Hỗ trợ giảng viên tổ chức bài tập/thi
- Ghi log hành vi và hỗ trợ phát hiện gian lận cơ bản

Điểm quan trọng:

- Đã chạy thực tế tại PTIT
- Theo tài liệu: hơn `800` sinh viên, hơn `30.000` lượt submit
- Kiến trúc `microservice`
- Có nhiều môi trường DB: `PostgreSQL`, `MySQL`, `SQL Server`
- Dùng `Kafka`, `Spring Boot`, `Eureka`, `Gateway`, Docker, nhiều node server

### 4.2. SQLArena trong DOCX

Đây là vision / bản nâng cấp sản phẩm.

SQLArena không chỉ là “trang chấm SQL”, mà là một platform hoàn chỉnh gồm:

- Nền tảng học SQL theo lộ trình
- AI sinh đề dựa trên dữ liệu cộng đồng
- AI feedback sau khi submit
- Battle Royale realtime
- Social Feed
- Achievement / Cosmetic
- Multi-tenant cho trường học và doanh nghiệp
- Chứng chỉ tùy biến theo tổ chức
- Enterprise API cho tuyển dụng / đào tạo
- Hỗ trợ NoSQL như MongoDB

Nói ngắn gọn:

- `Learn SQL` là nền móng chấm SQL
- `SQLArena` là product hóa nền móng đó thành một platform lớn

### 4.3. pipeline.html là gì?

Đây không phải toàn bộ hệ thống.

Nó chỉ mô tả một dây chuyền con:

- AI tự động sinh câu hỏi SQL
- Có bước planning, generation, clarity check, validation, retry, packaging
- Tối ưu để tạo khoảng `100 câu / tuần`
- Dùng `Gemini 2.0 Flash free tier`

Tức là:

- `PDF` = cả hệ thống gốc
- `DOCX` = cả hệ thống sản phẩm tương lai
- `pipeline.html` = một subsystem bên trong hệ thống tương lai

---

## 5. Kiến trúc sản phẩm theo DOCX

Theo tài liệu SQLArena, hệ thống hướng đến kiến trúc microservice với các thành phần:

### 5.1. Các service chính

- `API Gateway`
  - Định tuyến request, load balancing, CORS
- `Auth Service`
  - Xác thực, JWT, phân quyền, tenant isolation
- `Manager Service`
  - Người dùng, câu hỏi, lớp học, contest, chứng chỉ, analytics
- `Submit Service`
  - Điều phối chấm bài, AI feedback, leaderboard
- `Judge Service (MySQL/PgSQL/MSSQL)`
  - Thực thi SQL trên sandbox
- `Judge Service (MongoDB)`
  - Thực thi truy vấn NoSQL và so sánh JSON output
- `Battle Royale Service`
  - Realtime room, đồng bộ trạng thái, loại người chơi, chấm theo vòng
- `AI Orchestrator`
  - Sinh đề, validate, feedback, analytics suggestion
- `Enterprise API Service`
  - Assessment API, webhook, training API
- `Redis`
  - Realtime sync, leaderboard, session cache
- `Frontend Web`
  - UI người dùng + CMS + Dashboard

### 5.2. Công nghệ chính trong vision

- `Spring Boot`
- `PostgreSQL`
- `MySQL`
- `SQL Server`
- `MongoDB`
- `Kafka`
- `Redis`
- `WebSocket`
- `Docker`
- `ReactJS`
- `Tailwind CSS`
- `GPT API` hoặc LLM API

---

## 6. Triết lý kỹ thuật cốt lõi của hệ thống

### 6.1. Chấm bằng execution, không chấm bằng suy đoán

Đây là ý tưởng quan trọng nhất.

Thay vì nhìn câu SQL rồi “đoán” đúng/sai, hệ thống:

1. Tạo môi trường database sandbox
2. Nạp schema và seed data
3. Chạy SQL người dùng submit
4. Chạy đáp án chuẩn hoặc so sánh state/schema mong muốn
5. So sánh output thực tế

Ưu điểm:

- Khách quan
- Chấp nhận nhiều cách viết đúng
- Phù hợp cả DML và nhiều trường hợp DDL

### 6.2. Sandbox isolation

Mỗi bài nộp có một môi trường riêng để tránh:

- Người này phá dữ liệu của người kia
- Câu SQL độc hại ảnh hưởng hệ thống chung
- Xung đột bảng tạm hoặc procedure

Cơ chế được tài liệu mô tả:

- Prefix bảng ngẫu nhiên theo phiên
- User DB bị giới hạn quyền
- Blacklist query nguy hiểm
- Timeout
- Row limit
- Cleanup bắt buộc sau khi chấm

### 6.3. Hệ thống phải scale được

Tài liệu PDF mô tả triển khai theo:

- Nhiều service tách biệt
- Nhiều node server
- Kafka để xử lý submit đồng thời
- Eureka / Gateway để service discovery và routing

### 6.4. AI chỉ nên làm phần AI phù hợp

DOCX nhấn mạnh một nguyên tắc đúng:

- AI không nên quyết định “đúng/sai tuyệt đối” cho SQL
- AI phù hợp với:
  - Sinh câu hỏi
  - Viết feedback
  - Hỗ trợ analytics / đề xuất nội dung
  - Hỗ trợ admin ra quyết định

Tức là:

- `Deterministic` cho grading
- `AI` cho generation / explanation / adaptation

---

## 7. Pipeline AI Question Generator trong pipeline.html

Pipeline này là thiết kế tương đối chặt chẽ cho việc sinh câu hỏi hàng tuần.

### 7.1. Mục tiêu

- Sinh khoảng `100 câu / tuần`
- Chi phí gần `0 USD`
- Dùng `Gemini free tier`
- Có validation nhiều lớp
- Đảm bảo đủ số lượng câu bằng retry + fallback

### 7.2. 7 bước của pipeline

#### Bước 1. Skill Taxonomy DB

Xây “từ điển kiến thức”:

- Topic SQL
- Mức độ khó
- Lỗi phổ biến
- Few-shot seed
- Pattern câu hỏi tốt

Ý nghĩa:

- Không cho LLM sáng tác tự do từ số 0
- Cung cấp khung tri thức ổn định

#### Bước 2. Skill Target Selector

Quyết định tuần này nên sinh câu gì dựa trên:

- Pass rate
- Avg attempts
- Hint usage
- Avg time
- Config của admin

Ý tưởng tốt ở đây:

- Không chỉ nhìn pass rate
- Cố phân biệt:
  - Topic quá khó
  - Người học thiếu concept
  - Câu cũ mơ hồ

#### Bước 3. Question Planner

LLM tạo `blueprint` trước khi viết đề thật.

Blueprint gồm:

- Intent
- Target skill
- Schema hint
- Trap strategy
- Ambiguity risk

Đây là bước tốt vì:

- Ép AI lên kế hoạch
- Phát hiện mơ hồ sớm
- Giảm token lãng phí ở bước generation

#### Bước 4. Question Generator

LLM sinh câu hỏi hoàn chỉnh:

- `schema_sql`
- `seed_data_sql`
- `question_text`
- `answer_query`
- `expected_output`

Thêm ý tưởng `domain rotation`:

- Tuần nào cũng đổi domain dữ liệu
- Tránh đoán pattern

#### Bước 5. Clarity Check + Ground Truth Assertion

Hai lớp kiểm tra:

- `Linguistic Clarity Check`
  - Xem câu hỏi có mơ hồ không
- `Ground Truth Assertion`
  - Rule-based test đơn giản để bắt lỗi logic

Ý nghĩa:

- Không phụ thuộc hoàn toàn vào việc AI tự kiểm tra AI
- Có thêm lớp deterministic

#### Bước 6. Execution Engine Verify

Chạy đáp án thật trên DB sandbox.

Kiểm tra:

- Cú pháp
- Runtime
- Output
- FK consistency
- DDL handling

Đây là “cửa chặn cứng” đáng tin nhất.

#### Bước 7. Output + Metadata + Retry Policy

Đóng gói câu hỏi đã validate vào question bank.

Có:

- Metadata
- Retry escalation 3 cấp
- Archive fallback

Điểm mạnh:

- Không chỉ retry vô nghĩa
- Có phương án fallback để đủ SLA 100 câu/tuần

### 7.3. Đánh giá chung về pipeline.html

Điểm mạnh:

- Tư duy khá thực dụng
- Phân tầng rõ deterministic vs AI
- Có cold start strategy
- Có retry policy
- Có metadata / review queue

Điểm cần nhớ:

- Đây vẫn là bản thiết kế
- Không có nghĩa là repo hiện tại đã implement hết

---

## 8. Repo hiện tại `sqlarena-ai` thực chất là gì?

Repo này rất nhỏ và chỉ là prototype của phần “AI Question Generator”.

### 8.1. Luồng hiện tại

`POST /generate`:

1. FastAPI nhận request
2. Gọi `generate_pipeline(specs)`
3. Với từng spec (`easy`, `medium`, `hard`)
4. Gửi prompt sang Anthropic-compatible HTTP provider
5. Nhận JSON text từ LLM
6. Extract SQL bằng regex
7. Parse SQL bằng `sqlglot`
8. Lưu output ra file JSON

### 8.2. Thành phần hiện có

- `main.py`
  - FastAPI entrypoint
- `pipeline.py`
  - Flow generate + validate + save file
- `llm_gateway.py`
  - Gọi Anthropic-compatible HTTP provider
- `schema.json`
  - File schema dự kiến dùng cho prompt
- `docker-compose.yml`
  - Chạy API trong Docker

### 8.3. Stack repo hiện tại

- `FastAPI`
- `uvicorn`
- `Prefect`
- `httpx`
- `sqlglot`
- `python-dotenv`
- `Anthropic-compatible HTTP provider`

### 8.4. Repo hiện tại KHÔNG phải là gì

Repo này hiện chưa có:

- Auth
- Multi-tenant
- Battle Royale
- Social Feed
- AI Feedback Engine
- Enterprise API
- Dashboard analytics
- Judge service đa DB
- Kafka
- Redis
- Web frontend hoàn chỉnh
- NoSQL support thực sự
- Review queue thật
- Metadata store thật

Tức là repo hiện tại mới là:

- `một service Python nhỏ`
- tập trung vào `sinh câu hỏi SQL bằng LLM`
- chưa phải `SQLArena platform`

---

## 9. Mismatch giữa tài liệu và repo hiện tại

Đây là phần rất quan trọng để agent khác không bị hiểu sai.

### 9.1. Mismatch cấp độ scope

`DOCX` mô tả một platform rất lớn.

Repo hiện tại:

- chỉ là một prototype nhỏ
- gần với phần `pipeline.html`
- và còn đơn giản hơn `pipeline.html`

### 9.2. Mismatch bên trong chính repo

README nói:

- schema lấy từ `schema.json`

Nhưng code thực tế:

- `pipeline.py` đang hardcode `SCHEMA`
- `schema.json` hiện không được load vào runtime

README có nói đến bảng `inventory`, nhưng:

- `schema.json` có `inventory`
- `SCHEMA` hardcode trong `pipeline.py` lại không có `inventory`

### 9.3. Mismatch giữa “Prefect orchestration” và implementation

README nói theo kiểu:

- pipeline có orchestration

Nhưng code hiện tại:

- chạy tuần tự trong một vòng `for`
- chưa có orchestration thực sự đáng kể
- Prefect chủ yếu đang được dùng như decorator

### 9.4. Mismatch giữa pipeline.html và repo hiện tại

`pipeline.html` có:

- Taxonomy
- Target selector
- Planner
- Generator
- Clarity check
- Ground truth assertion
- Execution verify sâu
- Retry escalation
- Metadata hoàn chỉnh
- Review queue

Repo hiện tại chỉ có:

- Prompt đơn giản
- Generate raw output
- Parse SQL
- Validate cú pháp bằng `sqlglot`
- Save file JSON

Khoảng cách là rất lớn.

---

## 10. Đánh giá kỹ thuật repo hiện tại

### 10.1. Điểm tốt

- Repo nhỏ, dễ đọc
- Chạy local nhanh
- Ý tưởng rõ ràng
- Có API và Docker cơ bản
- Có sample output

### 10.2. Điểm yếu

- Prompt còn sơ sài
- Chỉ validate cú pháp SQL, chưa validate logic đáp án
- Dùng regex để extract JSON/SQL, dễ vỡ
- Không đọc schema từ file ngoài như docs mô tả
- Không có test
- Không có storage thực sự ngoài file JSON
- Không có review flow
- Error handling còn đơn giản
- Thiếu structured logging tổng thể
- Chưa có deterministic execution thật như vision mô tả

### 10.3. Rủi ro nếu ai đó hiểu nhầm repo hiện tại

Nếu đọc DOCX trước rồi nhìn repo, rất dễ tưởng rằng:

- platform lớn đã tồn tại trong code

Nhưng thực tế không phải.

Đây là điều phải giữ rất rõ khi review hay lên roadmap.

---

## 11. Thuật ngữ kỹ thuật quan trọng, giải nghĩa ngắn gọn

### 11.1. SQL

Ngôn ngữ dùng để hỏi và thao tác dữ liệu trong database.

### 11.2. Database

Kho chứa dữ liệu có cấu trúc.

### 11.3. Sandbox

Môi trường cô lập để chạy SQL an toàn, không phá dữ liệu thật.

### 11.4. Execution engine

Bộ phận chạy SQL thật rồi lấy kết quả thật để chấm.

### 11.5. DML

Nhóm lệnh thao tác dữ liệu:

- `SELECT`
- `INSERT`
- `UPDATE`
- `DELETE`

### 11.6. DDL

Nhóm lệnh thay đổi cấu trúc dữ liệu:

- `CREATE`
- `ALTER`
- `DROP`
- `TRUNCATE`

### 11.7. Microservice

Kiến trúc chia hệ thống thành nhiều service nhỏ, mỗi service làm một việc.

### 11.8. API Gateway

Cổng vào chung, nhận request rồi điều hướng đúng service.

### 11.9. Kafka

Hệ thống hàng đợi / truyền message để xử lý nhiều tác vụ đồng thời.

### 11.10. Redis

Bộ nhớ cực nhanh, phù hợp realtime, cache, leaderboard, pub/sub.

### 11.11. WebSocket

Cách giữ kết nối realtime giữa client và server, phù hợp game/phòng thi realtime.

### 11.12. Multi-tenant

Một nền tảng nhưng phục vụ nhiều tổ chức khác nhau, dữ liệu phải tách biệt.

### 11.13. Tenant isolation

Cơ chế đảm bảo dữ liệu tổ chức A không lẫn sang tổ chức B.

### 11.14. LLM

Mô hình ngôn ngữ lớn, dùng để sinh nội dung, phân tích text, viết feedback.

### 11.15. Analytics Dashboard

Bảng thống kê để admin/giảng viên nhìn toàn cảnh hành vi và kết quả học tập.

### 11.16. Gamification

Thêm yếu tố giống game để người dùng có động lực quay lại học.

### 11.17. Battle Royale

Chế độ thi đấu nhiều người theo thời gian thực, có loại dần hoặc xếp hạng trực tiếp.

### 11.18. NoSQL

Kiểu cơ sở dữ liệu không đi theo bảng quan hệ cổ điển như SQL; trong docs nói đến MongoDB.

---

## 12. Những gì có vẻ là “đã có thật” và “chưa chắc đã có thật”

### 12.1. Đã có nền tảng thực tế

Theo PDF, hệ thống Learn SQL gốc:

- đã triển khai thật
- đã có người dùng thật
- đã có multi-node
- đã có microservice
- đã có chấm SQL thực thi thật

### 12.2. DOCX là tài liệu thiết kế / mở rộng

DOCX mô tả nhiều tính năng nâng cấp:

- AI refresh pool
- Battle Royale
- Social feed
- NoSQL support
- Enterprise API
- Achievement / Cosmetic

Không nên mặc định tất cả các mục trong DOCX đều đã tồn tại đầy đủ trong code hiện tại.

### 12.3. Repo hiện tại mới là prototype

Repo hiện tại cho thấy:

- một nỗ lực nhỏ để dựng phần AI generation
- không đủ bằng chứng để kết luận toàn bộ SQLArena đã được code

---

## 13. Nếu tiếp tục phát triển repo này, nên hiểu nó là pha nào?

Pha hợp lý nhất để xem repo hiện tại:

- `prototype / proof-of-concept`
- cho subsystem `AI question generation`

Không nên xem nó là:

- bản production-ready
- bản thể hiện full platform

### 13.1. Roadmap logic nếu muốn đi tiếp

1. Làm rõ mục tiêu
   - Chỉ muốn hoàn thiện `AI pipeline`?
   - Hay muốn dựng dần `SQLArena platform`?

2. Nếu chỉ tập trung AI pipeline
   - Load schema từ file
   - Chuẩn hóa format output
   - Bỏ regex mong manh
   - Thêm execution-based validation
   - Thêm metadata
   - Thêm review state
   - Thêm tests

3. Nếu muốn tiến tới product lớn
   - Tách architecture rõ hơn
   - Chọn stack thống nhất
   - Xác định service boundaries
   - Xác định phần nào kế thừa Learn SQL, phần nào viết mới

---

## 14. Checklist cho agent tiếp theo khi review

### 14.1. Trước khi code

- Đừng giả định repo này là toàn bộ SQLArena
- Phân biệt rõ `vision docs` và `implementation`
- Xác định đang làm ở tầng nào:
  - docs alignment
  - prototype AI
  - execution engine
  - full platform

### 14.2. Nếu review tính đúng đắn

Nên kiểm tra:

- LLM output có luôn là JSON hợp lệ không
- SQL extract có bền không
- Validation hiện tại có chỉ là syntax-check không
- Schema thực tế có đồng bộ giữa docs / schema.json / code không
- Output JSON có đủ metadata để trace/debug không

### 14.3. Nếu review kiến trúc

Nên hỏi:

- Có muốn tiếp tục giữ Python prototype không?
- Hay chỉ dùng repo này làm PoC rồi chuyển sang service khác?
- AI pipeline chạy batch hay real-time?
- Source of truth cho schema / taxonomy / question bank là gì?
- Review queue ở đâu?
- Archive fallback ở đâu?

### 14.4. Nếu review gap sản phẩm

Các gap lớn nhất so với DOCX:

- Chưa có execution engine thật
- Chưa có multi-db judge
- Chưa có analytics-driven target selection
- Chưa có planner/clarity/assertion layers như HTML
- Chưa có feedback engine
- Chưa có battle royale / social / cert / tenant / enterprise API

---

## 15. Tóm tắt cuối cùng cho người mới vào đọc

### 15.1. Một câu

Đây là một ý tưởng rất lớn về nền tảng học và đánh giá SQL/NoSQL, nhưng repo hiện tại chỉ mới hiện thực hóa một phần nhỏ của subsystem AI sinh câu hỏi.

### 15.2. Ba lớp cần nhớ

- `Learn SQL (PDF)`:
  - hệ thống gốc đã chạy thật, trọng tâm là chấm SQL tự động
- `SQLArena (DOCX)`:
  - vision sản phẩm hoàn chỉnh, mở rộng mạnh về AI, game hóa, SaaS, enterprise
- `sqlarena-ai repo`:
  - prototype nhỏ cho AI question generation

### 15.3. Phán đoán thực dụng

Nếu cần tiếp tục công việc kỹ thuật ngay:

- Hãy xem repo hiện tại như một PoC
- Dùng DOCX làm `product vision`
- Dùng PDF làm `legacy/proven foundation`
- Dùng `pipeline.html` làm `target design` cho subsystem AI generation

---

## 16. Confidence / assumptions

Confidence: `0.92`

Assumptions đã dùng:

- `SQLArena.docx` là tài liệu mô tả sản phẩm/vision chứ không phải chứng cứ toàn bộ đã implement
- `pipeline.html` là bản mô tả subsystem AI pipeline, không phải code runtime thật
- Repo `sqlarena-ai` là prototype độc lập hoặc nhánh thử nghiệm của phần AI generation

Nếu muốn chắc hơn nữa ở bước tiếp theo, cần:

- so sánh với repo gốc của Learn SQL nếu có
- xác minh có tồn tại codebase microservice Java/Spring tương ứng với PDF/DOCX hay không

