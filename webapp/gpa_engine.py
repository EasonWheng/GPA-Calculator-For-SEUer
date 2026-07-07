import json
import math
from typing import List, Dict, Optional, Tuple, Any

# ================== 等级制映射 (百分制) ==================
GRADE_MAP: Dict[str, int] = {
    "优": 95,
    "良": 85,
    "中": 75,
    "及格": 65,
    "不及格": 55,
}

# ================== 等级制映射 (4.8 绩点制) ==================
GRADE_TO_GPA_4_8: Dict[str, float] = {
    "优": 4.5,
    "良": 3.5,
    "中": 2.5,
    "及格": 1.5,
    "不及格": 0.0,
}

# ================== 等级制映射 (4.0 绩点制) ==================
GRADE_TO_GPA_4_0: Dict[str, float] = {
    "优": 4.0,
    "良": 3.0,
    "中": 2.0,
    "及格": 1.0,
    "不及格": 0.0,
}

# ================== 默认配置 ==================
DEFAULT_KEYWORDS = [
    "电路", "信号", "通信", "电子", "数字", "模拟", "电磁",
    "概率", "随机", "线性代数", "数学分析", "复变",
    "计组", "计算机组织", "操作系统", "linux", "微机系统",
    "无线", "网络",
]

DEFAULT_EXCLUDES = [
    "电子信息类专业学习概论",
]


# ================== 安全数值解析 ==================
def parse_float_safe(x: Any) -> Optional[float]:
    """从任意值安全提取 float；无法提取或为哨兵值时返回 None"""
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() in ("待评教", "na", "n/a"):
            return None
        v = float(s)
        if v < 0 or math.isinf(v) or math.isnan(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


# ================== JSON 提取 ==================
def extract_json_objects(text: str) -> List[str]:
    """从混合文本中提取所有顶级 JSON 对象字符串（brace counting）"""
    objs, brace, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if brace == 0:
                start = i
            brace += 1
        elif ch == "}":
            brace -= 1
            if brace == 0 and start is not None:
                objs.append(text[start:i + 1])
                start = None
    return objs


def load_rows_from_string(text: str) -> List[Dict]:
    """从 JSON 字符串中提取所有成绩行（同 load_all_rows_from_txt 逻辑）"""
    rows: List[Dict] = []
    for js in extract_json_objects(text):
        try:
            data = json.loads(js)
        except json.JSONDecodeError:
            continue

        datas = data.get("datas")
        if not isinstance(datas, dict):
            continue

        page_rows: List[Dict] = []
        xscjcx = datas.get("xscjcx")
        if isinstance(xscjcx, dict):
            page_rows = xscjcx.get("rows", [])

        if not page_rows:
            for key in datas:
                v = datas[key]
                if isinstance(v, dict) and "rows" in v:
                    page_rows = v["rows"]
                    break

        for r in page_rows:
            if isinstance(r, dict):
                rows.append(r)

    return rows


# ================== 总评成绩估算 (5 层回退) ==================
def estimate_zcj_from_row(row: Dict) -> Tuple[Optional[float], bool, str]:
    """返回 (分值或None, 是否估算, 描述信息)"""
    # 层 1: ZCJ 数值
    zcj_raw = row.get("ZCJ")
    zcj_val = parse_float_safe(zcj_raw)
    if zcj_val is not None:
        return zcj_val, False, "ZCJ"

    # 层 1b: ZCJ 等级文字
    if isinstance(zcj_raw, str) and zcj_raw.strip() in GRADE_MAP:
        return float(GRADE_MAP[zcj_raw.strip()]), False, "ZCJ (等级)"

    # 层 2: DJCJMC 等级成绩名称
    djcmc = row.get("DJCJMC")
    if isinstance(djcmc, str) and djcmc.strip() in GRADE_MAP:
        return float(GRADE_MAP[djcmc.strip()]), False, "DJCJMC"

    # 层 3: XSZCJMC 显示总成绩名称
    xszcj = row.get("XSZCJMC")
    xszcj_val = parse_float_safe(xszcj)
    if xszcj_val is not None:
        return xszcj_val, False, "XSZCJMC"
    if isinstance(xszcj, str) and xszcj.strip() in GRADE_MAP:
        return float(GRADE_MAP[xszcj.strip()]), False, "XSZCJMC (等级)"

    # 层 4: _DISPLAY 字段
    for disp_key in ("QMCJ_DISPLAY", "PSCJ_DISPLAY", "SYCJ_DISPLAY", "SJCJ_DISPLAY", "QZCJ_DISPLAY"):
        disp_val = row.get(disp_key)
        if isinstance(disp_val, str) and disp_val.strip() in GRADE_MAP:
            return float(GRADE_MAP[disp_val.strip()]), True, disp_key
    for disp_key in ("QMCJ_DISPLAY", "PSCJ_DISPLAY", "SYCJ_DISPLAY", "SJCJ_DISPLAY", "QZCJ_DISPLAY"):
        disp_val = parse_float_safe(row.get(disp_key))
        if disp_val is not None:
            return disp_val, True, disp_key

    # 层 5: 分项成绩加权估算
    components = [
        ("QMCJ", "QMCJXS"), ("PSCJ", "PSCJXS"), ("QZCJ", "QZCJXS"),
        ("SYCJ", "SYCJXS"), ("SJCJ", "SJCJXS"),
    ]
    total_w, weighted_s = 0.0, 0.0
    for sk, wk in components:
        s = parse_float_safe(row.get(sk))
        if s is None:
            continue
        w = parse_float_safe(row.get(wk)) or parse_float_safe(row.get(f"{wk}_DISPLAY"))
        if w is None:
            continue
        weighted_s += s * w
        total_w += w

    if total_w > 0:
        return weighted_s / total_w, True, "分项加权估算"
    return None, True, "无可用成绩数据"


# ================== 课程抽取 ==================
def extract_official_courses(rows: List[Dict]) -> List[Dict]:
    """从行数据中提取必修+限选课程"""
    courses: List[Dict] = []
    for r in rows:
        if not r.get("XSKCM") and not r.get("KCM"):
            continue
        if r.get("KCXZDM_DISPLAY") not in ("必修", "限选"):
            continue
        try:
            credit = float(r.get("XF", 0))
        except (ValueError, TypeError):
            continue
        if credit <= 0:
            continue

        score, is_est, msg = estimate_zcj_from_row(r)
        if score is None:
            continue

        courses.append({
            "name": r.get("XSKCM") or r.get("KCM", ""),
            "type": r.get("KCXZDM_DISPLAY"),
            "score": score,
            "credit": credit,
            "estimated": is_est,
            "estimate_reason": msg,
        })
    return courses


# ================== Core Major 判断 ==================
def is_core_major(name: str, keywords: List[str], excludes: List[str]) -> bool:
    """判断课程名是否匹配核心专业课关键词（支持显式排除）"""
    if not name:
        return False
    for ex in excludes:
        if ex.strip() and ex.strip() in name:
            return False
    low = name.lower()
    return any(k.strip().lower() in low for k in keywords if k.strip())


# ================== 加权计算 ==================
def weighted_avg(courses: List[Dict]) -> Optional[float]:
    s = sum(c["score"] * c["credit"] for c in courses)
    w = sum(c["credit"] for c in courses)
    return s / w if w else None


# ================== 4.0 GPA 转换 ==================
def score_to_gpa_4_0(score: float) -> float:
    """百分制 → 4.0 美式 GPA"""
    if score >= 93: return 4.0
    if score >= 90: return 3.7
    if score >= 87: return 3.3
    if score >= 83: return 3.0
    if score >= 80: return 2.7
    if score >= 77: return 2.3
    if score >= 73: return 2.0
    if score >= 70: return 1.7
    if score >= 67: return 1.3
    if score >= 63: return 1.0
    return 0.0


# ================== 4.8 GPA 转换 (东南大学官方) ==================
def score_to_gpa_4_8(score: float) -> float:
    """百分制 → 4.8 东大官方绩点（区间转换法）"""
    if score >= 96: return 4.8
    if score >= 93: return 4.5
    if score >= 90: return 4.0
    if score >= 86: return 3.8
    if score >= 83: return 3.5
    if score >= 80: return 3.0
    if score >= 76: return 2.8
    if score >= 73: return 2.5
    if score >= 70: return 2.0
    if score >= 66: return 1.8
    if score >= 63: return 1.5
    if score >= 60: return 1.0
    return 0.0


def weighted_gpa(courses: List[Dict], gpa_type: str) -> Optional[float]:
    """统一 GPA 加权计算入口"""
    converter = score_to_gpa_4_8 if gpa_type == "4.8" else score_to_gpa_4_0
    total, w = 0.0, 0.0
    for c in courses:
        total += converter(c["score"]) * c["credit"]
        w += c["credit"]
    return total / w if w else None


# ================== 单科绩点获取 ==================
def course_gpa(score: float, gpa_type: str) -> float:
    """返回单科绩点"""
    if gpa_type == "4.8":
        return score_to_gpa_4_8(score)
    return score_to_gpa_4_0(score)


# ================== 主计算入口 ==================
def calculate_all(json_text: str, keywords: List[str],
                  excludes: List[str], gpa_type: str) -> Dict[str, Any]:
    """一站式计算：返回完整结果 dict"""
    warnings: List[str] = []
    rows = load_rows_from_string(json_text)

    if not rows:
        return {
            "error": True,
            "message": "未能从输入中解析出任何成绩数据。请检查 JSON 格式。",
        }

    official = extract_official_courses(rows)

    # 收集警告
    for c in official:
        if c["estimated"]:
            warnings.append(f"{c['name']}: 成绩从「{c['estimate_reason']}」获取 ({c['score']})")

    official_avg_100 = weighted_avg(official)
    official_gpa = weighted_gpa(official, gpa_type) if official else None

    core = [c for c in official if is_core_major(c["name"], keywords, excludes)]
    core_avg_100 = weighted_avg(core)
    core_gpa = weighted_gpa(core, gpa_type) if core else None

    # 为每门课附加单科绩点
    for c in official:
        c["gpa"] = course_gpa(c["score"], gpa_type)
    for c in core:
        c["gpa"] = course_gpa(c["score"], gpa_type)

    return {
        "error": False,
        "gpa_type": gpa_type,
        "total_rows_parsed": len(rows),
        "official_courses": official,
        "official_count": len(official),
        "official_avg_100": round(official_avg_100, 3) if official_avg_100 else None,
        "official_gpa": round(official_gpa, 3) if official_gpa else None,
        "core_courses": core,
        "core_count": len(core),
        "core_avg_100": round(core_avg_100, 3) if core_avg_100 else None,
        "core_gpa": round(core_gpa, 3) if core_gpa else None,
        "warnings": warnings,
    }


def get_defaults() -> Dict[str, Any]:
    """返回默认关键词和排除列表"""
    return {
        "keywords": DEFAULT_KEYWORDS,
        "excludes": DEFAULT_EXCLUDES,
    }
