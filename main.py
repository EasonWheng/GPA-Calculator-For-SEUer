import json
import math
from typing import List, Dict, Optional

# ================== 等级制映射 ==================
GRADE_MAP = {
    "优": 95,
    "良": 85,
    "中": 75,
    "及格": 65,
    "不及格": 55
}
# ================== Core Major 排除课程（显式黑名单） ==================
EXCLUDE_COURSES = [
    "电子信息类专业学习概论"
]
# ================== Core Major 关键词 ==================
CORE_KEYWORDS = [
    "电路", "信号", "通信", "电子", "数字", "模拟", "电磁",
    "概率", "随机", "线性代数", "数学分析", "复变",
    "计组", "计算机组织", "操作系统", "linux","微机系统",
    "无线", "网络"
]

# ================== JSON 提取 ==================
def extract_json_objects(text: str) -> List[str]:
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

def load_all_rows_from_txt(path: str) -> List[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"错误：找不到文件 {path}，请将成绩数据保存为 成绩.txt 后重试。")
        return []

    rows = []
    for js in extract_json_objects(text):
        try:
            data = json.loads(js)
        except json.JSONDecodeError:
            continue

        datas = data.get("datas")
        if not isinstance(datas, dict):
            continue

        page_rows = []
        # 优先 datas.xscjcx.rows
        xscjcx = datas.get("xscjcx")
        if isinstance(xscjcx, dict):
            page_rows = xscjcx.get("rows", [])
        # 回退：遍历 datas 下其他 key
        if not page_rows:
            for key in datas:
                v = datas[key]
                if isinstance(v, dict) and "rows" in v:
                    page_rows = v["rows"]
                    break

        # 过滤非 dict 的行（防御空占位行）
        for r in page_rows:
            if isinstance(r, dict):
                rows.append(r)

    return rows

# ================== Official 课程抽取 ==================
def extract_official_courses(rows: List[Dict]) -> List[Dict]:
    courses = []

    for r in rows:
        # 跳过缺少关键字段的空行（如 API 返回的占位行）
        if not r.get("XSKCM") and not r.get("KCM"):
            continue

        if r.get("KCXZDM_DISPLAY") not in ("必修", "限选"):
            continue

        credit_raw = r.get("XF")
        try:
            credit = float(credit_raw)
        except:
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
            "estimate_reason": msg
        })

    return courses

# ================== Core Major 判断 ==================
def is_core_major(name: str) -> bool:
    if not name:
        return False

    # 显式排除水课
    for ex in EXCLUDE_COURSES:
        if ex in name:
            return False

    low = name.lower()
    return any(k.lower() in low for k in CORE_KEYWORDS)

# ================== 加权计算 ==================
def weighted_avg(courses: List[Dict]) -> Optional[float]:
    s = sum(c["score"] * c["credit"] for c in courses)
    w = sum(c["credit"] for c in courses)
    return s / w if w else None

# ================== 100 → 4.0（美式常用） ==================
def score_to_gpa(score: float) -> float:
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

def weighted_gpa_4(courses: List[Dict]) -> Optional[float]:
    total, w = 0.0, 0.0
    for c in courses:
        total += score_to_gpa(c["score"]) * c["credit"]
        w += c["credit"]
    return total / w if w else None



def parse_float_safe(x):
    try:
        if x is None: return None
        s = str(x).strip()
        if s == "" or s.lower() in ("待评教", "na", "n/a"): return None
        v = float(s)
        # 过滤哨兵值和非正规数值
        if v < 0 or math.isinf(v) or math.isnan(v):
            return None
        return v
    except:
        return None


def estimate_zcj_from_row(row):
    """
    输入：单条记录（dict）
    输出： (zcj_value (float or None), is_estimate (bool), message (str))
    """
    # 1. 尝试 ZCJ（总成绩）
    zcj_raw = row.get("ZCJ")
    zcj_val = parse_float_safe(zcj_raw)
    if zcj_val is not None:
        return zcj_val, False, "ZCJ present as numeric"

    # 1b. ZCJ 可能是文字等级
    if isinstance(zcj_raw, str) and zcj_raw.strip() in GRADE_MAP:
        return float(GRADE_MAP[zcj_raw.strip()]), False, "ZCJ mapped from grade label"

    # 2. 尝试 DJCJMC（等级成绩名称，如"优"/"良"/"中"），常见于五级制课程
    djcmc = row.get("DJCJMC")
    if isinstance(djcmc, str) and djcmc.strip() in GRADE_MAP:
        return float(GRADE_MAP[djcmc.strip()]), False, "DJCJMC mapped from grade label"

    # 3. 尝试 XSZCJMC（显示总成绩名称），可能是数字字符串或等级文字
    xszcj = row.get("XSZCJMC")
    xszcj_val = parse_float_safe(xszcj)
    if xszcj_val is not None:
        return xszcj_val, False, "XSZCJMC present as numeric"
    if isinstance(xszcj, str) and xszcj.strip() in GRADE_MAP:
        return float(GRADE_MAP[xszcj.strip()]), False, "XSZCJMC mapped from grade label"

    # 4. 尝试所有 _DISPLAY 字段（分项成绩显示值，有时是等级文字如"优"）
    for disp_key in ("QMCJ_DISPLAY", "PSCJ_DISPLAY", "SYCJ_DISPLAY", "SJCJ_DISPLAY", "QZCJ_DISPLAY"):
        disp_val = row.get(disp_key)
        if isinstance(disp_val, str) and disp_val.strip() in GRADE_MAP:
            return float(GRADE_MAP[disp_val.strip()]), True, f"{disp_key} mapped from grade label"

    # 4b. 尝试所有 _DISPLAY 字段中的数字值
    for disp_key in ("QMCJ_DISPLAY", "PSCJ_DISPLAY", "SYCJ_DISPLAY", "SJCJ_DISPLAY", "QZCJ_DISPLAY"):
        disp_val = parse_float_safe(row.get(disp_key))
        if disp_val is not None:
            return disp_val, True, f"{disp_key} present as numeric"

    # 5. 从分项成绩加权估算
    comp_names = [
        ("QMCJ", "QMCJXS"),
        ("PSCJ", "PSCJXS"),
        ("QZCJ", "QZCJXS"),
        ("SYCJ", "SYCJXS"),
        ("SJCJ", "SJCJXS"),
    ]

    total_weight = 0.0
    weighted_sum = 0.0
    have_any = False
    missing_weight_for_score = None

    for score_key, weight_key in comp_names:
        s = parse_float_safe(row.get(score_key))
        w_raw = row.get(weight_key)
        w = parse_float_safe(w_raw)
        if s is None:
            continue
        if w is None:
            # 权重可能以 _DISPLAY 形式存在
            w_disp = row.get(f"{weight_key}_DISPLAY")
            w = parse_float_safe(w_disp)
        if w is None:
            missing_weight_for_score = (score_key, weight_key)
            continue
        have_any = True
        weighted_sum += s * w
        total_weight += w

    if not have_any:
        if missing_weight_for_score is not None:
            return None, True, f"Missing weight {missing_weight_for_score[1]} for present component {missing_weight_for_score[0]}"
        return None, True, "No component scores available to estimate"

    if total_weight <= 0:
        return None, True, "Total weight is zero or invalid"

    z_est = weighted_sum / total_weight
    return z_est, True, f"Estimated from components; total_weight={total_weight}"


# ================== 主程序 ==================
def main():
    print("""========================
DISCLAIMER / 免责声明
========================


【简体中文】

本项目仅供学习与个人使用。

1. 数据来源说明  
本工具不提供、也不包含任何绕过登录、认证、安全机制或访问控制的方式。  
用户必须自行通过合法途径登录本人有权限访问的官方成绩查询系统，并手动获取属于本人的成绩数据。  
所有输入到本程序的数据，均应来自用户对自身数据的合法访问。

2. 用户责任  
用户需自行确保：  
- 其所使用的数据仅限本人合法可访问的数据；  
- 使用本工具的行为符合所在学校及相关系统的使用条款、管理规定及法律法规；  
- 因不当使用、越权访问或违反相关规定所产生的任何后果，均由用户本人承担。

3. 非官方声明  
本项目与任何高校、教育机构或教务管理系统均无任何隶属、合作、授权或背书关系。

4. 无担保声明  
本软件按“原样（AS IS）”提供，不附带任何形式的明示或暗示担保。  
程序计算结果（包括但不限于均分、GPA 等）仅供参考，不保证与任何官方成绩评定标准或结果一致。

5. 责任限制  
在任何情况下，作者均不对因使用本软件而产生的直接或间接损失、数据问题或其他后果承担任何责任。

一旦使用本软件，即视为您已阅读、理解并同意上述免责声明内容。


------------------------------------------------------------


[English]

This project is provided for educational and personal use only.

1. Data Source  
This tool does NOT provide any method to bypass authentication, security mechanisms, or access control.  
Users must legally log in to their own official academic system and manually obtain grade data that they are authorized to access.  
All data supplied to this program must originate from the user's legitimate access to their own records.

2. User Responsibility  
Users are solely responsible for ensuring that:  
- The data used belongs to themselves and is lawfully obtained;  
- Their use of this tool complies with institutional policies, terms of service, and applicable laws;  
- Any consequences arising from misuse, unauthorized access, or policy violations are borne by the user.

3. No Affiliation  
This project is NOT affiliated with, endorsed by, or associated with any university, academic institution, or administrative system.

4. No Warranty  
This software is provided "AS IS", without warranty of any kind.  
All calculated results (including averages or GPA) are for reference only and may not reflect official evaluation standards.

5. Limitation of Liability  
Under no circumstances shall the author be held liable for any direct, indirect, incidental, or consequential damages resulting from the use of this software.

By using this software, you acknowledge that you have read, understood, and agreed to this disclaimer.


------------------------------------------------------------


【繁體中文】

本專案僅供學習與個人使用。

1. 資料來源說明  
本工具不提供、亦不包含任何繞過登入、驗證、安全機制或存取控制的方法。  
使用者必須自行透過合法方式登入本人有權限存取的官方成績查詢系統，並手動取得屬於自身的成績資料。  
所有輸入至本程式的資料，皆應來自使用者對自身資料的合法存取。

2. 使用者責任  
使用者須自行確保：  
- 所使用之資料僅限本人合法可存取的資料；  
- 使用本工具之行為符合所屬學校及相關系統之使用條款、管理規範與法律法規；  
- 因不當使用、越權存取或違反相關規定所造成之一切後果，概由使用者自行承擔。

3. 非官方聲明  
本專案與任何大學、教育機構或教務管理系統皆無任何隸屬、合作、授權或背書關係。

4. 無擔保聲明  
本軟體以「現狀（AS IS）」方式提供，不附帶任何明示或默示之擔保。  
所有計算結果（包括但不限於平均分、GPA）僅供參考，並不保證與任何官方評定結果一致。

5. 責任限制  
在任何情況下，作者均不對因使用本軟體所導致的任何直接或間接損失承擔責任。

一經使用本軟體，即表示您已閱讀、理解並同意本免責聲明之全部內容。\n""")
    print("\033[1;36mPress ENTER to ACCEPT the terms and continue\033[0m")
    print("\033[1;36mPress ENTER to ACCEPT the terms and continue\033[0m")
    print("\033[1;36mPress ENTER to ACCEPT the terms and continue\033[0m")
    input("\033[1;36m请按任意键接受条款，进入程序：\033[0m\n\n")

    rows = load_all_rows_from_txt("成绩.txt")

    # ===== ① Official 全量课程 =====
    official = extract_official_courses(rows)

    print("========== Official 参与计算的全部课程 ==========\n")
    for c in official:
        print(f"- {c['name']} | {c['type']} | 成绩={c['score']} | 学分={c['credit']}")

    official_avg = weighted_avg(official)

    print("\n🎓 Official（必修 + 限选）加权均分（100制）：")
    print(f"{official_avg:.3f}" if official_avg else "N/A")

    # ===== ② Core Major 子集 =====
    core = [c for c in official if is_core_major(c["name"])]

    print("\n========== Core Major 课程（Official 子集） ==========\n")
    for c in core:
        print(f"- {c['name']} | 成绩={c['score']} | 学分={c['credit']}")

    core_avg_100 = weighted_avg(core)
    core_avg_4 = weighted_gpa_4(core)

    print("\n🎓 Core Major 加权均分（100制）：")
    print(f"{core_avg_100:.3f}" if core_avg_100 else "N/A")

    print("\n🎓 Core Major GPA（4.0制，美式）：")
    input("请按任意键三次退出：")
    input("请按任意键三次退出：")
    input("请按任意键三次退出：")


if __name__ == "__main__":
    main()