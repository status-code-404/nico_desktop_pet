"""
Memory system — dimensions, collection names, constants.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════
# Dimension definitions
# ═══════════════════════════════════════════════════════════════

DIMENSIONS = {
    "episodic": {
        "name": "时间线",
        "desc": "所有对话和系统动作的完整时间线记录，按时间检索",
        "collection": "mem_episodic",
    },
    "identity": {
        "name": "身份",
        "desc": "名字、语言、所在地、时区等基础信息",
        "collection": "mem_identity",
    },
    "work": {
        "name": "工作",
        "desc": "职业、行业、技能、项目、工作习惯",
        "collection": "mem_work",
    },
    "family": {
        "name": "家庭",
        "desc": "家人、亲密关系、家庭事件",
        "collection": "mem_family",
    },
    "health": {
        "name": "健康",
        "desc": "作息、饮食、运动、身体状态、喝水提醒",
        "collection": "mem_health",
    },
    "learning": {
        "name": "学习",
        "desc": "课程、学习目标、笔记主题、知识积累",
        "collection": "mem_learning",
    },
    "life": {
        "name": "生活",
        "desc": "出行、天气、消费、生活事件、定时任务",
        "collection": "mem_life",
    },
    "interests": {
        "name": "兴趣",
        "desc": "爱好、游戏、阅读、媒体偏好",
        "collection": "mem_interests",
    },
    "goals": {
        "name": "目标",
        "desc": "短期目标、长期计划、优先级",
        "collection": "mem_goals",
    },
    "preferences": {
        "name": "偏好",
        "desc": "沟通风格、提醒偏好、交互习惯",
        "collection": "mem_preferences",
    },
}

# Dimension order for batch classification
DIMENSION_KEYS = list(DIMENSIONS.keys())

# Profile fields stored in SQLite (structured, upsert)
PROFILE_FIELDS = [
    # identity
    "name", "language", "location", "timezone",
    # work
    "job_title", "industry", "skills", "work_hours",
    # family
    "family_members", "family_notes",
    # health
    "sleep_pattern", "diet_preferences", "exercise_routine", "health_notes",
    # learning
    "current_courses", "study_goals",
    # life
    "commute_routes", "weather_city", "shopping_preferences",
    # interests
    "hobbies", "favorite_media", "games_played",
    # goals
    "short_term_goals", "long_term_goals",
    # preferences
    "communication_style", "reminder_style", "autonomy_level",
]

# ═══════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from server.config import settings

MEMORY_DIR = os.path.join(settings.data_dir, "memory_db")
CHROMA_DIR = os.path.join(MEMORY_DIR, "chroma")
SQLITE_PATH = os.path.join(MEMORY_DIR, "profile.sqlite3")

os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

# Embedding model name (local, fast: < 50ms per query on CPU)
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
