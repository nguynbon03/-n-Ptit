# Ke hoach tich hop file Excel vao du an SQLArena AI

Tai lieu nay tom tat vai tro cac file code hien co va cac huong co the sua code de dua file Excel `Master_SQL_Dataset_All_Sources_2.xlsx` vao pipeline sinh de.

Luu y: hien tai code trong repo chua doc file Excel. File Excel dang la dataset nguon rieng, con pipeline hien tai sinh cau hoi dua tren `schema.json`, `taxonomy.py` va LLM provider.

## 1. Tong quan luong chay hien tai

Luong chay chinh:

```text
Client / Swagger
  -> main.py
  -> pipeline.py
  -> llm_gateway.py
  -> schema_loader.py + taxonomy.py
  -> clarity_checker.py
  -> execution_engine.py
  -> question_bank.py
  -> data/questions.db
```

Neu goi API:

```text
POST /generate
```

thi `main.py` goi `generate_pipeline()` trong `pipeline.py`. Pipeline se:

1. Load schema tu `schema.json`.
2. Lay danh sach topic tu `taxonomy.py`.
3. Goi LLM de tao blueprint.
4. Goi LLM de sinh cau hoi SQL.
5. Check do ro rang cua de.
6. Chay SQL trong SQLite memory de verify.
7. Luu cau hoi vao SQLite database `data/questions.db`.

## 2. Vai tro tung file code

### `main.py`

Day la entrypoint FastAPI.

Tac dung chinh:

- Tao app FastAPI.
- Khai bao endpoint `/health`.
- Khai bao endpoint `/generate` de sinh cau hoi.
- Khai bao endpoint `/tasks/{task_id}` de xem trang thai task background.
- Khai bao endpoint `/questions`, `/questions/{question_id}`, `/questions/{question_id}/status`.
- Khai bao endpoint `/stats`.
- Khai bao endpoint `/verify-sql` de verify SQL rieng.

Lien quan den Excel:

- Hien chua nhan `excel_path`.
- Hien request `/generate` chi co `specs` va `questions_per_spec`.
- Neu muon cho user chon sinh de tu Excel, co the them field vao request, vi du `source="excel"` hoac `excel_path`.

### `pipeline.py`

Day la file quan trong nhat cua luong sinh de.

Tac dung chinh:

- Dieu phoi 7 buoc sinh cau hoi.
- Load schema.
- Chon topic/difficulty.
- Goi planner de tao blueprint.
- Goi generator prompt de sinh cau hoi.
- Check clarity.
- Verify SQL.
- Luu cau hoi vao question bank.

Lien quan den Excel:

- Hien chua doc Excel.
- Hien prompt sinh cau hoi lay schema tu `schema_loader.generate_ddl(schema)`.
- Few-shot example lay tu `taxonomy.get_few_shot_example()`.
- Neu tich hop Excel, day la noi can chen source example tu Excel vao prompt.

### `llm_gateway.py`

Day la lop trung gian goi LLM.

Tac dung chinh:

- Doc `.env`.
- Ho tro 2 provider:
  - `anthropic`
  - `gemini`
- Voi Anthropic-compatible HTTP provider, goi endpoint `/api/generate`.
- Voi Gemini, goi Google Generative AI SDK.

Lien quan den Excel:

- Khong can sua neu chi dua Excel vao prompt.
- Chi can sua neu muon co logic provider/model rieng cho viec xu ly Excel.

### `question_planner.py`

Day la file tao blueprint truoc khi sinh cau hoi hoan chinh.

Tac dung chinh:

- Dinh nghia model `QuestionBlueprint`.
- Build prompt cho LLM de tao blueprint.
- Parse JSON LLM tra ve.
- Validate difficulty, ambiguity risk, schema tables.

Lien quan den Excel:

- Co the dua thong tin Excel vao prompt planner.
- Vi du: dua `noi dung`, `database_schema`, `tu khoa` cua mot dong Excel vao de LLM tao blueprint giong phong cach do.

### `taxonomy.py`

Day la file dinh nghia topic, difficulty config va few-shot example dang hard-code.

Tac dung chinh:

- Cung cap topic pool:
  - `SELECT_BASIC`
  - `WHERE_FILTER`
  - `JOIN_INNER`
  - `JOIN_LEFT`
  - `GROUP_BY`
  - `HAVING`
  - `SUBQUERY`
  - `AGGREGATE`
  - `ORDER_LIMIT`
  - `WINDOW_FUNCTION`
  - `CASE_WHEN`
  - `NULL_HANDLING`
- Cung cap config easy/medium/hard.
- Cung cap few-shot example theo topic va difficulty.

Lien quan den Excel:

- Excel co cot `the loai bai`, `ky thuat su dung`, `tu khoa`.
- Can map cac gia tri nay sang topic cua `taxonomy.py`.
- Co the thay few-shot hard-code bang few-shot lay tu Excel, hoac uu tien Excel neu co.

### `schema_loader.py`

Day la file load schema va sinh DDL/seed data.

Tac dung chinh:

- Doc `schema.json`.
- Sinh SQL `CREATE TABLE`.
- Sinh SQL `INSERT` mau.
- Chuyen type ve SQLite type.
- Sap xep thu tu tao bang theo dependency don gian.

Lien quan den Excel:

- Hien chi doc schema JSON co format:

```json
{
  "tables": {
    "employees": {
      "columns": {
        "id": "INTEGER PRIMARY KEY"
      }
    }
  }
}
```

- Excel lai co `database_schema` dang text, vi du:

```text
Employee (id int, salary int)
Person (personId int, lastName varchar, firstName varchar) | Address (...)
```

- Neu muon dung schema trong Excel that su, can them parser bien text nay thanh dict giong `schema.json`.

### `schema.json`

Day la schema mac dinh hien tai.

Tac dung chinh:

- Dinh nghia cac bang:
  - `employees`
  - `departments`
  - `products`
  - `sales`
  - `inventory`

Lien quan den Excel:

- Dang khong dong bo voi Excel.
- Excel moi dong co schema rieng, con `schema.json` la mot schema co dinh.
- Neu khong sua code parser schema Excel, pipeline van se sinh de theo schema nay.

### `clarity_checker.py`

Day la file check de bai co ro rang khong.

Tac dung chinh:

- Check cau hoi co rong khong.
- Check cau qua ngan.
- Check co action word nhu `find`, `list`, `show`, `count`.
- Check dai tu mo ho.
- Check mot so mau mau thuan.
- Tra ve `is_clear`, `score`, `issues`.

Lien quan den Excel:

- Co the dung de check cot `noi dung` hoac cau hoi LLM sinh ra.
- Hien dang check tieng Anh tot hon tieng Viet, vi action words la tieng Anh.
- Neu Excel/de sinh bang tieng Viet, can bo sung action words tieng Viet.

### `execution_engine.py`

Day la sandbox verify SQL bang SQLite in-memory.

Tac dung chinh:

- Chan mot so lenh nguy hiem: `DROP`, `TRUNCATE`, `ATTACH`, `DETACH`.
- Tao SQLite database tam.
- Chay DDL.
- Chay seed SQL.
- Chay answer SQL.
- Tra ve output, row count, error, duration.
- Timeout 5 giay.

Lien quan den Excel:

- Neu dung schema trong Excel, phai bien `database_schema` thanh DDL SQLite hop le.
- Excel hien chua co seed data rieng tach biet, nen verify se kho neu chi co schema text.
- Neu muon verify that, can co them seed data hoac cho LLM sinh seed data tu schema Excel.

### `question_bank.py`

Day la lop luu cau hoi vao SQLite database.

Tac dung chinh:

- Tao database `data/questions.db`.
- Tao bang `questions`.
- Luu cau hoi sinh ra.
- List/get question.
- Update status.
- Lay stats.
- Lay fallback question da approved/archived.

Lien quan den Excel:

- Hien khong luu source Excel.
- Neu muon trace cau hoi sinh ra tu dong Excel nao, nen them metadata, vi du:
  - `source_excel_id`
  - `source_name`
  - `source_title`
  - `source_row_number`

Co the khong can sua schema database neu luu vao `metadata_json`.

### `retry_policy.py`

Day la file xu ly retry khi LLM sinh cau hoi loi.

Tac dung chinh:

- Attempt 2: yeu cau LLM sinh cau don gian hon.
- Attempt 3+: yeu cau sinh cau toi gian.
- Neu het retry, thu lay archived fallback.

Lien quan den Excel:

- Co the giu nguyen.
- Neu dung Excel lam source, retry prompt nen giu lai thong tin source row de LLM khong mat context.

### `requirements.txt`

Day la danh sach dependency Python.

Hien co:

```text
prefect
httpx
python-dotenv
sqlglot
uvicorn
fastapi
pydantic
google-generativeai
aiofiles
```

Lien quan den Excel:

- Can them `openpyxl` neu doc `.xlsx` truc tiep.
- Neu dung pandas thi them `pandas` va `openpyxl`, nhung voi nhu cau hien tai `openpyxl` la du.
- Test can `pytest`, nhung hien `pytest` chua co trong requirements.

### `Dockerfile`

Day la cau hinh build container API.

Tac dung chinh:

- Dung image `python:3.11-slim`.
- Cai dependency tu `requirements.txt`.
- Copy code vao container.
- Chay `uvicorn main:app`.

Lien quan den Excel:

- Neu Excel can nam trong container, Dockerfile hien `COPY . .` se copy ca file Excel vao container.
- Neu file Excel lon hoac khong muon copy vao image, nen mount volume qua docker-compose.

### `docker-compose.yml`

Day la cau hinh chay service API bang Docker Compose.

Tac dung chinh:

- Build image tu Dockerfile.
- Map port `8000:8000`.
- Mount `./Output:/app/Output`.
- Mount `./data:/app/data`.
- Cau hinh env cho Anthropic-compatible HTTP/Gemini.

Lien quan den Excel:

- Neu muon Excel thay doi ben ngoai container va container doc duoc, nen mount file/folder Excel.
- Vi du mount:

```yaml
volumes:
  - ./Master_SQL_Dataset_All_Sources_2.xlsx:/app/Master_SQL_Dataset_All_Sources_2.xlsx
```

### `README.md`

Day la tai lieu huong dan chay du an.

Luu y:

- README dang noi output JSON vao `Output/`.
- Code hien tai luu cau hoi vao SQLite `data/questions.db`.
- README va code co ve khong hoan toan dong bo.

### `docs.md` va `pipeline.html`

Day la tai lieu/mo ta pipeline.

Tac dung chinh:

- Giai thich y tuong pipeline.
- Co nhieu noi noi ve taxonomy, cold start, metadata, quality control.

Lien quan den Excel:

- Co the xem Excel la "human seed" hoac dataset seed ban dau cho cold start.

## 3. Tinh trang file Excel hien tai

File:

```text
Master_SQL_Dataset_All_Sources_2.xlsx
```

Thong tin da kiem tra:

```text
So sheet: 1
So dong data: 168
So cot: 9
Khong co cot nao bi trong toan bo
Khong co id trung
```

Cot hien co:

```text
id
nguon
de bai
noi dung
boi canh
the loai bai
ky thuat su dung
database_schema
tu khoa
```

Phan bo difficulty:

```text
Easy: 91
Medium: 57
Hard: 20
```

Nguon:

```text
LeetCode: 51
HackerRank: 50
DataLemur: 46
StrataScratch: 21
```

Nhom ky thuat:

```text
Aggregation & Grouping: 78
Basic Select & Filtering: 56
Window Functions & Ranking: 15
Conditional Logic & Functions: 13
Joins & Subqueries: 6
```

Van de chinh:

- Excel co nhieu schema khac nhau theo tung bai.
- Code hien tai chi dung mot schema co dinh trong `schema.json`.
- Excel chua co cot answer SQL rieng.
- Excel chua co cot seed data rieng.
- Code hien tai chua co loader cho Excel.

## 4. Cac huong sua de dua Excel vao pipeline

## Huong A: Excel lam few-shot/context, van dung `schema.json`

Day la huong de lam nhat va it rui ro nhat.

Y tuong:

- Doc Excel.
- Chon 1-3 dong Excel co difficulty/topic gan voi yeu cau.
- Dua cac dong do vao prompt nhu vi du tham khao.
- LLM sinh cau hoi moi nhung van dua tren schema mac dinh `schema.json`.

Luong moi:

```text
Excel row examples
  -> normalize difficulty/topic
  -> inject vao prompt
  -> LLM sinh cau hoi moi theo schema.json
  -> verify bang SQLite
  -> save vao question_bank
```

File can sua/them:

```text
requirements.txt       them openpyxl
excel_loader.py        file moi de doc Excel
pipeline.py            them logic lay source examples
taxonomy.py            co the them mapper topic
```

Uu diem:

- It sua code.
- Khong can parse schema Excel thanh DDL.
- Verify SQL van chay duoc vi van dung `schema.json`.
- Phu hop de demo nhanh "sinh de dua tren dataset Excel".

Nhuoc diem:

- Cau hoi sinh ra khong dung schema goc cua bai trong Excel.
- Excel chi anh huong phong cach, topic, pattern, khong phai database that.

Nen lam khi:

- Can co ket qua nhanh.
- Team chua co yeu cau bat buoc phai dung schema tung dong Excel.
- Muc tieu la sinh de moi theo phong cach dataset.

## Huong B: Excel lam taxonomy/few-shot va co map topic chat hon

Day la phien ban nang cap cua Huong A.

Y tuong:

- Tao mapper tu cot `ky thuat su dung` va `tu khoa` sang topic noi bo.
- Khi user yeu cau `easy`, `medium`, `hard`, pipeline chon row Excel cung difficulty.
- Khi chon topic, uu tien keyword cu the.

Bang map goi y:

```text
Aggregation & Grouping
  -> GROUP_BY
  -> AGGREGATE
  -> HAVING

Basic Select & Filtering
  -> SELECT_BASIC
  -> WHERE_FILTER
  -> ORDER_LIMIT

Window Functions & Ranking
  -> WINDOW_FUNCTION

Conditional Logic & Functions
  -> CASE_WHEN
  -> NULL_HANDLING

Joins & Subqueries
  -> JOIN_INNER
  -> JOIN_LEFT
  -> SUBQUERY
```

Keyword override goi y:

```text
LEFT JOIN      -> JOIN_LEFT
INNER JOIN     -> JOIN_INNER
HAVING         -> HAVING
GROUP BY       -> GROUP_BY
COUNT(), SUM() -> AGGREGATE
ORDER BY       -> ORDER_LIMIT
ROW_NUMBER()   -> WINDOW_FUNCTION
DENSE_RANK()   -> WINDOW_FUNCTION
CASE WHEN      -> CASE_WHEN
DISTINCT       -> SELECT_BASIC
WHERE          -> WHERE_FILTER
```

File can sua/them:

```text
excel_loader.py
excel_topic_mapper.py
pipeline.py
taxonomy.py
```

Uu diem:

- Excel anh huong tot hon den loai cau hoi sinh ra.
- Van khong can parse schema Excel.
- De test tung phan.

Nhuoc diem:

- Van chua dung schema tung bai trong Excel.
- Can can than tranh map sai topic.

Nen lam khi:

- Muon pipeline sinh de can bang theo dataset Excel.
- Muon dung Excel lam nguon tri thuc cho taxonomy.

## Huong C: Dung schema cua tung dong Excel

Day la huong dung hon nhung kho hon.

Y tuong:

- Doc cot `database_schema`.
- Parse text schema thanh dict giong `schema.json`.
- Sinh DDL SQLite tu schema do.
- Sinh seed data tu schema do.
- Dua DDL/seed vao prompt.
- LLM sinh question + answer SQL tren schema cua dong Excel.
- Verify answer SQL bang `execution_engine.py`.

Luong moi:

```text
Excel row
  -> parse database_schema
  -> schema dict
  -> generate DDL
  -> generate seed data
  -> prompt LLM
  -> answer SQL
  -> verify SQLite
  -> save question
```

File can sua/them:

```text
requirements.txt
excel_loader.py
excel_schema_parser.py
schema_loader.py
pipeline.py
execution_engine.py  co the giu nguyen neu DDL hop le
```

Vi du input Excel:

```text
Employee (id int, salary int)
```

Can parse thanh:

```json
{
  "tables": {
    "Employee": {
      "columns": {
        "id": "INTEGER",
        "salary": "INTEGER"
      }
    }
  }
}
```

Van de can xu ly:

- Ten bang/cot co viet hoa/viet thuong.
- Type SQL khac nhau: `int`, `varchar`, `decimal`, `date`.
- Primary key trong Excel khong phai luc nao cung ro.
- Nhieu schema ngan cach bang dau `|`.
- Khong co foreign key ro rang.
- Khong co seed data rieng.
- LLM co the sinh SQL dung syntax nhung output rong.

Uu diem:

- Cau hoi sinh ra bam schema Excel that.
- Co gia tri hon neu dataset Excel la nguon chuan cua team.

Nhuoc diem:

- Can lam parser va validation can than.
- Rui ro loi cao hon.
- Can nhieu test.

Nen lam khi:

- Team yeu cau cau hoi moi phai dua tren schema trong Excel.
- Co thoi gian lam parser/schema validation.

## Huong D: Import Excel thanh question bank

Huong nay khac voi sinh de moi. No dung Excel nhu ngan hang cau hoi co san.

Y tuong:

- Doc Excel.
- Moi dong tao mot record trong `questions`.
- Luu `noi dung` lam `question_text`.
- Luu `database_schema` vao metadata hoac parse thanh `schema_sql`.
- Status co the la `archived` hoac `approved`.
- Pipeline co the dung cac cau nay lam fallback/few-shot.

File can sua/them:

```text
excel_importer.py
question_bank.py      co the khong can sua neu luu metadata_json
```

Uu diem:

- Dung duoc Excel ngay lam data seed.
- Co ich cho fallback khi LLM fail.
- It anh huong den pipeline sinh de.

Nhuoc diem:

- Excel chua co answer SQL rieng nen khong the verify day du.
- Khong phai "sinh de moi", ma la import de co san.

Nen lam khi:

- Team can nap dataset Excel vao he thong truoc.
- Can co question bank ban dau.

## 5. Huong khuyen nghi

Nen di theo lo trinh:

```text
Buoc 1: Huong A
  Excel lam few-shot/context, van dung schema.json.

Buoc 2: Huong B
  Them topic mapper de chon example dung hon.

Buoc 3: Huong D
  Import Excel thanh question bank/fallback neu can.

Buoc 4: Huong C
  Parse schema tung dong Excel neu team bat buoc dung schema Excel.
```

Ly do:

- Huong A/B co the lam nhanh va it pha code cu.
- Van giu duoc verify SQL hien tai.
- Chua phai giai bai toan kho la parse schema text va tao seed data.
- Co the demo som rang Excel da anh huong den cau hoi sinh ra.

## 6. Thay doi toi thieu cho version dau

Neu chi lam ban dau de chung minh Excel tich hop duoc, nen lam toi thieu:

```text
1. Them openpyxl vao requirements.txt
2. Them excel_loader.py
3. Them ham load_excel_examples(path)
4. Them ham normalize_difficulty()
5. Them ham map_excel_topic()
6. Sua pipeline.py de lay 1 example tu Excel theo difficulty/topic
7. Chen example vao prompt generator
8. Luu source Excel vao metadata_json
```

Khong nen sua ngay:

```text
schema_loader.py
execution_engine.py
question_bank.py schema database
Dockerfile
```

Tru khi team bat buoc.

## 7. De xuat format object sau khi doc Excel

Mot row Excel nen duoc chuan hoa thanh dict:

```json
{
  "source_id": "LC-SQL-0176",
  "source": "LeetCode",
  "title": "Second Highest Salary",
  "problem_text": "...",
  "domain_context": "Quan tri Nhan su & Tien luong",
  "difficulty": "medium",
  "category": "Basic Select & Filtering",
  "mapped_topic": "SELECT_BASIC",
  "schema_text": "Employee (id int, salary int)",
  "keywords": ["DISTINCT"]
}
```

Sau do prompt co the them:

```text
Reference examples from existing SQL dataset:

Example 1:
- Source: LeetCode
- Difficulty: Medium
- Topic: Basic Select & Filtering
- Keywords: DISTINCT
- Original title: Second Highest Salary
- Original schema: Employee (id int, salary int)
- Original problem summary: ...

Use these examples only as inspiration. Do not copy the original question.
Generate a new question using the provided project schema.
```

## 8. Ranh gioi can thong nhat voi team

Can hoi team may diem truoc khi code:

1. Excel la nguon de sinh cau hoi moi hay la question bank co san?
2. Cau hoi sinh ra co bat buoc dung schema trong cot `database_schema` khong?
3. Co can sinh cau hoi bang tieng Viet khong?
4. Co can luu trace ve dong Excel goc khong?
5. Co can import tat ca Excel vao database khong?
6. Co can answer SQL cho cac bai goc trong Excel khong?

Neu cau tra loi la "chi can dung Excel de sinh de moi", bat dau bang Huong A/B la hop ly nhat.

