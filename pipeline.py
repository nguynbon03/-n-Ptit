"""
pipeline.py — 7-step SQL question generation pipeline (plain Python, no cloud dependency).
"""

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from clarity_checker import check_clarity
from excel_loader import get_excel_row
from excel_schema_sync import schema_from_excel_row
from execution_engine import verify_in_sandbox
from llm_gateway import LLMGateway
from novelty_checker import check_novelty
from question_bank import QuestionBank
from question_planner import QuestionBlueprint, plan_question
from retry_policy import get_retry_prompt, should_use_archive
from semantic_checker import check_semantic_consistency
from schema_loader import generate_ddl, generate_seed, load_schema
from taxonomy import get_difficulty_config, get_few_shot_example, get_topic_pool

load_dotenv(override=False)

_BASE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)

_GENERATOR_PROMPT = """You are an expert SQL question author.

Database schema (DDL):
{schema_sql}

Question blueprint:
- Difficulty: {difficulty}
- Topic: {topic}
- Intent: {intent}
- Required SQL constructs: {constructs}
- Trap strategy: {trap_strategy}

Few-shot example:
{few_shot}

Excel reference (use its domain, skill and intent, but write a new question):
{excel_reference}

Seed data available:
{seed_sql}

Generate ONE SQL exam question that matches the blueprint exactly.

Use SQLite syntax only. Begin question_text with a clear action verb such as Find, List,
Show, Count, Calculate, Display, Return, or Identify.

Consistency rules:
- The question, topic, blueprint intent, seed data, and answer SQL must test the same skill.
- Preserve edge cases demonstrated by the provided seed data.
- If the topic is JOIN_LEFT, the answer must use LEFT JOIN and the seed data must include
  at least one unmatched row from the left table so the result contains NULL values.
- If the topic is WINDOW_FUNCTION, use ROW_NUMBER, RANK, DENSE_RANK, or NTILE with OVER.
  When filtering by a window result, calculate it in a CTE or subquery first and filter
  by its alias in the outer query. Never place a window function directly in WHERE.
  Follow this valid SQLite shape when ranking rows:
  WITH ranked AS (
    SELECT ..., DENSE_RANK() OVER (PARTITION BY ... ORDER BY ... DESC) AS rank_value
    FROM ...
  )
  SELECT ... FROM ranked WHERE rank_value <= ...;
- Use the Excel reference as source material, but do not merely paraphrase its question text.

Return ONLY this JSON object:
{{
  "question_text": "<clear exam-style question for students>",
  "schema_sql": "<full CREATE TABLE statements needed>",
  "seed_sql": "<INSERT statements to populate realistic data>",
  "answer_sql": "<correct SQL answer>",
  "expected_output_description": "<brief description of what the result set looks like>"
}}
"""

_EXCEL_TOPIC_MAP = {
    "basic select & filtering": "WHERE_FILTER",
    "aggregation & grouping": "GROUP_BY",
    "window functions & ranking": "WINDOW_FUNCTION",
    "conditional logic & functions": "CASE_WHEN",
    "joins & subqueries": "JOIN_INNER",
}


def build_excel_signature(row: dict, schema: dict, topic: str) -> dict:
    content = str(row.get("content") or "").casefold()
    edge_cases = []
    if topic == "JOIN_LEFT":
        edge_cases.append("At least one left-table row has no matching right-table row")
    if "null" in content:
        edge_cases.append("NULL values must affect the expected result")
    return {
        "domain": row.get("context"),
        "difficulty": str(row.get("category") or "").lower(),
        "target_skill": topic,
        "technique_group": row.get("technique"),
        "keywords": row.get("keywords"),
        "tables": {
            table_name: list(table_def.get("columns", {}).keys())
            for table_name, table_def in schema.get("tables", {}).items()
        },
        "required_edge_cases": edge_cases,
        "novelty_requirement": (
            "Create a different analytical goal. Do not reproduce the source task or merely "
            "replace verbs. For JOIN_LEFT, prefer identifying or summarizing unmatched rows."
        ),
    }


def load_excel_target(excel_path: str, excel_id: str) -> tuple[dict, str, str, dict]:
    row = get_excel_row(excel_path, excel_id)
    schema = schema_from_excel_row(row)
    difficulty = str(row.get("category") or "medium").strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    technique = str(row.get("technique") or "").strip().casefold()
    keywords = str(row.get("keywords") or "").upper()
    content = str(row.get("content") or "").casefold()
    topic = _EXCEL_TOPIC_MAP.get(technique, "SELECT_BASIC")
    keyword_topics = (
        ("LEFT JOIN", "JOIN_LEFT"),
        ("INNER JOIN", "JOIN_INNER"),
        ("DENSE_RANK", "WINDOW_FUNCTION"),
        ("ROW_NUMBER", "WINDOW_FUNCTION"),
        ("HAVING", "HAVING"),
        ("GROUP BY", "GROUP_BY"),
        ("CASE", "CASE_WHEN"),
        ("NULL", "NULL_HANDLING"),
    )
    for keyword, keyword_topic in keyword_topics:
        if keyword in keywords:
            topic = keyword_topic
            break
    left_join_signals = (
        "not present",
        "report null",
        "return null",
        "even if there is no",
        "whether or not",
        "including those without",
    )
    if technique == "joins & subqueries" and any(signal in content for signal in left_join_signals):
        topic = "JOIN_LEFT"
    window_signals = (
        "top three",
        "top 3",
        "unique salaries for that department",
        "dense_rank",
        "row_number",
        "ranked within",
    )
    if any(signal in content for signal in window_signals):
        topic = "WINDOW_FUNCTION"
    return schema, difficulty, topic, row


# ---------------------------------------------------------------------------
# Step functions (plain Python — no Prefect cloud)
# ---------------------------------------------------------------------------

def step1_load_taxonomy(schema_path: str) -> tuple[dict, list]:
    schema = load_schema(schema_path)
    topics = get_topic_pool()
    logger.info("Step1: taxonomy loaded. tables=%d topics=%d", len(schema.get("tables", {})), len(topics))
    return schema, topics


def step2_select_target(topics: list, difficulty: str, stats: dict) -> dict:
    get_difficulty_config(difficulty)

    existing_by_topic: dict = {k: v for k, v in stats.get("by_topic", {}).items()}
    sorted_topics = sorted(topics, key=lambda t: existing_by_topic.get(t["topic"], 0))
    chosen = sorted_topics[0] if sorted_topics else (topics[0] if topics else {"topic": "SELECT_BASIC"})
    chosen_topic = chosen["topic"] if isinstance(chosen, dict) else chosen

    logger.info("Step2: target selected. topic=%s difficulty=%s", chosen_topic, difficulty)
    return {"topic": chosen_topic, "difficulty": difficulty}


def step3_plan_question(
    difficulty: str,
    topic: str,
    schema: dict,
    llm: LLMGateway,
    excel_reference: dict | None = None,
) -> QuestionBlueprint:
    source_context = (
        build_excel_signature(excel_reference, schema, topic)
        if excel_reference
        else None
    )
    blueprint = plan_question(
        difficulty=difficulty,
        topic=topic,
        schema=schema,
        llm=llm,
        source_context=source_context,
    )
    logger.info("Step3: blueprint created. skill=%s", blueprint.target_skill)
    return blueprint


def step4_generate_question(
    blueprint: QuestionBlueprint,
    topic: str,
    schema: dict,
    llm: LLMGateway,
    attempt: int = 1,
    override_prompt: str | None = None,
    excel_reference: dict | None = None,
) -> dict:
    schema_sql = generate_ddl(schema)
    seed_sql = generate_seed(schema)
    few_shot = get_few_shot_example(topic, blueprint.difficulty)
    reference_text = "None"
    if excel_reference:
        reference_text = json.dumps(
            build_excel_signature(excel_reference, schema, topic),
            ensure_ascii=False,
        )

    base_prompt = _GENERATOR_PROMPT.format(
        schema_sql=schema_sql,
        difficulty=blueprint.difficulty,
        topic=topic,
        intent=blueprint.intent,
        constructs=blueprint.target_skill,
        trap_strategy=blueprint.trap_strategy,
        few_shot=few_shot,
        excel_reference=reference_text,
        seed_sql=seed_sql,
    )

    prompt = base_prompt
    if override_prompt:
        prompt += f"\n\nRetry feedback:\n{override_prompt}"
    raw = llm.generate("generator", prompt, expect_json=True)

    if raw.startswith("ERROR:"):
        raise ValueError(f"LLM generation failed: {raw}")

    # Strip markdown fences if present
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        inner = []
        inside = False
        for line in lines:
            if line.startswith("```") and not inside:
                inside = True
                continue
            if line.startswith("```") and inside:
                break
            if inside:
                inner.append(line)
        clean = "\n".join(inner).strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM did not return valid JSON: {exc}\nRaw: {raw[:300]}")

    missing = {"question_text", "schema_sql", "seed_sql", "answer_sql"} - parsed.keys()
    if missing:
        raise ValueError(f"LLM JSON missing keys: {missing}")

    parsed["expected_output"] = parsed.pop("expected_output_description", "")
    parsed["difficulty"] = blueprint.difficulty
    parsed["topic"] = topic
    parsed["generation_attempt"] = attempt
    parsed["blueprint"] = blueprint

    logger.info("Step4: question generated. topic=%s attempt=%d", topic, attempt)
    return parsed


def step5_clarity_check(question_text: str) -> dict:
    result = check_clarity(question_text)
    logger.info("Step5: clarity is_clear=%s score=%s", result.get("is_clear"), result.get("score"))
    return result


def step6_execution_verify(schema_sql: str, seed_sql: str, answer_sql: str) -> dict:
    result = verify_in_sandbox(schema_sql, seed_sql, answer_sql)
    logger.info("Step6: execution valid=%s rows=%s error=%s", result.get("valid"), result.get("row_count"), result.get("error"))
    return result


def step7_save_to_bank(question_data: dict, bank: QuestionBank) -> str:
    question_id = bank.save(question_data)
    logger.info("Step7: saved id=%s", question_id)
    return question_id


# ---------------------------------------------------------------------------
# Single question generation with retry
# ---------------------------------------------------------------------------

def _generate_one(
    difficulty: str,
    topic: str,
    schema: dict,
    llm: LLMGateway,
    bank: QuestionBank,
    max_retries: int = 3,
    excel_reference: dict | None = None,
) -> dict:
    blueprint = step3_plan_question(
        difficulty=difficulty,
        topic=topic,
        schema=schema,
        llm=llm,
        excel_reference=excel_reference,
    )
    last_prompt: str | None = None

    for attempt in range(1, max_retries + 2):
        if should_use_archive(attempt, max_retries):
            fallback = bank.get_archived_fallback(difficulty=difficulty, topic=topic)
            if fallback:
                logger.warning("Retries exhausted, using archive fallback id=%s", fallback["id"])
                return {"question_id": fallback["id"], "valid": bool(fallback["valid"]), "skipped": True}
            logger.error("Retries exhausted, no archive fallback. difficulty=%s topic=%s", difficulty, topic)
            return {"question_id": None, "valid": False, "skipped": True}

        override = get_retry_prompt(last_prompt or "", attempt, difficulty, topic) if attempt > 1 else None

        try:
            question_data = step4_generate_question(
                blueprint=blueprint, topic=topic, schema=schema,
                llm=llm, attempt=attempt, override_prompt=override,
                excel_reference=excel_reference,
            )
            last_prompt = override
        except Exception as exc:
            logger.warning("Step4 failed attempt=%d: %s", attempt, exc)
            last_prompt = f"The previous output was invalid: {exc}"
            continue

        try:
            clarity = step5_clarity_check(question_data["question_text"])
            question_data["clarity_score"] = clarity.get("score", 0.0)
            if clarity.get("warnings"):
                question_data.setdefault("metadata", {})["clarity_warnings"] = clarity["warnings"]
            if not clarity.get("is_clear", True):
                logger.warning(
                    "Clarity failed attempt=%d blocking_issues=%s",
                    attempt,
                    clarity.get("blocking_issues", clarity.get("issues")),
                )
                last_prompt = (
                    "The previous question failed clarity validation. Rewrite it without "
                    f"these issues: {clarity.get('blocking_issues', clarity.get('issues', []))}"
                )
                continue
        except Exception as exc:
            logger.warning("Step5 failed attempt=%d: %s", attempt, exc)
            question_data["clarity_score"] = None

        if excel_reference:
            novelty = check_novelty(
                question_data["question_text"],
                str(excel_reference.get("content") or ""),
            )
            question_data.setdefault("metadata", {})["novelty"] = novelty
            if not novelty["is_novel"]:
                logger.warning(
                    "Novelty failed attempt=%d score=%s threshold=%s",
                    attempt,
                    novelty["score"],
                    novelty["threshold"],
                )
                last_prompt = (
                    f"The previous question was too similar to the source "
                    f"(similarity={novelty['score']}). Create a different analytical goal; "
                    "do not list the same output columns or paraphrase the source task."
                )
                continue

        try:
            verify_result = step6_execution_verify(
                question_data["schema_sql"], question_data["seed_sql"], question_data["answer_sql"],
            )
            question_data["valid"] = verify_result.get("valid", False)
            question_data["expected_output"] = verify_result.get("output", [])
            question_data.setdefault("metadata", {})["verify"] = {
                "row_count": verify_result.get("row_count"),
                "duration_ms": verify_result.get("duration_ms"),
                "error": verify_result.get("error"),
            }
            if not verify_result.get("valid", False):
                logger.warning("Execution failed attempt=%d error=%s", attempt, verify_result.get("error"))
                last_prompt = (
                    "The previous answer SQL failed in SQLite. Correct the SQL while keeping "
                    f"the blueprint and required topic. SQLite error: {verify_result.get('error')}"
                )
                continue

            semantic = check_semantic_consistency(
                question_text=question_data["question_text"],
                answer_sql=question_data["answer_sql"],
                seed_sql=question_data["seed_sql"],
                topic=topic,
                output=verify_result.get("output", []),
            )
            question_data.setdefault("metadata", {})["semantic"] = semantic
            if not semantic["is_consistent"]:
                logger.warning(
                    "Semantic validation failed attempt=%d issues=%s",
                    attempt,
                    semantic["issues"],
                )
                last_prompt = (
                    "The previous question and answer failed semantic validation. Fix every "
                    f"issue and keep the required topic: {semantic['issues']}"
                )
                continue
        except Exception as exc:
            logger.warning("Step6 failed attempt=%d: %s", attempt, exc)
            question_data["valid"] = False

        if excel_reference:
            question_data.setdefault("metadata", {})["excel_source"] = {
                "id": excel_reference.get("id"),
                "row": excel_reference.get("excel_row"),
                "source": excel_reference.get("source"),
            }

        question_id = step7_save_to_bank(question_data, bank)
        return {"question_id": question_id, "valid": question_data.get("valid", False), "skipped": False}

    return {"question_id": None, "valid": False, "skipped": True}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_pipeline(
    specs: list[str] = ["easy", "medium", "hard"],
    questions_per_spec: int = 1,
    schema_path: str | None = None,
    excel_id: str | None = None,
    excel_path: str | None = None,
) -> dict:
    schema_path = schema_path or str(_BASE_DIR / "schema.json")
    excel_path = excel_path or str(_BASE_DIR / "Master_SQL_Dataset_All_Sources_2_1.xlsx")
    llm = LLMGateway()
    bank = QuestionBank()

    excel_reference = None
    if excel_id:
        schema, excel_difficulty, excel_topic, excel_reference = load_excel_target(
            excel_path, excel_id
        )
        topics = [{"topic": excel_topic}]
        specs = [excel_difficulty]
        questions_per_spec = 1
    else:
        schema, topics = step1_load_taxonomy(schema_path)
    stats = bank.get_stats()

    generated = 0
    valid_count = 0
    failed = 0
    question_ids: list[str] = []

    for difficulty in specs:
        for _ in range(questions_per_spec):
            target = step2_select_target(topics=topics, difficulty=difficulty, stats=stats)
            topic = target["topic"]

            result = _generate_one(
                difficulty=difficulty,
                topic=topic,
                schema=schema,
                llm=llm,
                bank=bank,
                excel_reference=excel_reference,
            )

            if result["question_id"] is None:
                failed += 1
            else:
                if not result["skipped"]:
                    generated += 1
                question_ids.append(result["question_id"])
                if result["valid"]:
                    valid_count += 1

            stats = bank.get_stats()

    return {
        "generated": generated,
        "valid": valid_count,
        "failed": failed,
        "question_ids": [qid for qid in question_ids if qid],
        "stats": bank.get_stats(),
        "excel_id": excel_id,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_pipeline()
    print(json.dumps(result, indent=2, ensure_ascii=False))
